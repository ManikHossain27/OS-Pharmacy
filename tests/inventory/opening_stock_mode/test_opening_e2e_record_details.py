"""Opening Stock mode - END-TO-END: create form -> cart -> checkout -> Complete -> Inventory Record -> Inventory
Details (spec sections 42-44.1).

Each journey verifies EVERY stage against the oracle and then proves that the record it just created is the one
displayed in Inventory Details, line by line (matched by the unique batch numbers entered). A mismatch at one stage
never hides a mismatch at another - all are reported together. The journey helpers are the Default-mode suite's:
after BTP+VAT/Box is derived the two modes share one calculation and one set of screens.

These tests create real inventories on the target environment.
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.shared_journey import assert_journey, buy_journey, check_payment_dialog, journey
from tests.inventory.scenario_params import scenario_params
from utils.inventory_assertions import Verifier, check_details_free
from utils.inventory_scenarios import LineSpec, Scenario
from utils.helpers import money
from utils.opening_scenarios import CART_SHAPES, e2e_scenarios

pytestmark = [pytest.mark.inventory, pytest.mark.e2e]


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - end to end")
class TestJourneyMatrix:

    @pytest.mark.parametrize("scenario", scenario_params(e2e_scenarios(), default_marks=(pytest.mark.regression,)))
    @allure.story("Create -> cart -> checkout -> complete -> Inventory Details: every figure traced to the oracle")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_full_journey(self, flow, scenario):
        for bug in scenario.known_bugs:
            allure.dynamic.issue(bug)
        j, verifiers = journey(flow, scenario)
        assert_journey(verifiers)


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - end to end")
class TestDetailsContent:

    @allure.story("Details names the source mode: Inventory Mode = Opening Stock (spec 44)")
    @pytest.mark.regression
    def test_details_shows_opening_stock_mode(self, flow):
        j = flow.fill_cart(Scenario("mode", (LineSpec("P0", box_qty=1, retail=100),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        assert dlg.pricing_breakdown().get("Inventory Mode", "").strip() == "Opening Stock"

    @allure.story("Details shows Free Qty in the Qty column as 'N pc free' and Total (+ Final) in the Price column (spec 44.1)")
    @pytest.mark.regression
    def test_details_shows_free_and_total(self, flow):
        j = flow.fill_cart(Scenario("free", (LineSpec("P0", box_qty=2, retail=100, free_qty=3),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        row = dlg.item_row_by_batch(j.batches[0])
        v = Verifier("details free / total")
        check_details_free(v, row, 3, j.batches[0])
        v.contains("Price column shows 'Total:'", (row or {}).get("Price", ""), "Total")
        v.assert_all()

    @allure.story("Details exposes every required pricing field and item column")
    @pytest.mark.regression
    def test_details_required_fields_and_columns(self, flow):
        j = flow.fill_cart(Scenario("cols", (LineSpec("P0", box_qty=1, retail=100),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        dlg.wait_loaded()
        assert not dlg.missing_pricing_breakdown_fields(), dlg.missing_pricing_breakdown_fields()
        assert not dlg.missing_item_columns(), dlg.missing_item_columns()

    @allure.story("The saved BTP+VAT/Box on Details is the derived value (retail 100 at 20 % -> 80), not the retail price")
    @pytest.mark.regression
    def test_details_btp_is_derived_value(self, flow):
        j = flow.fill_cart(Scenario("derived", (LineSpec("P0", box_qty=3, retail=100, opening_pct=20),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        row = dlg.item_row_by_batch(j.batches[0])
        v = Verifier("derived BTP on details")
        v.any_number("BTP+VAT column = 80 per box / 240 total", (row or {}).get("BTP+VAT", ""), [80, 240])
        v.any_number("Retail Price column = 100", (row or {}).get("Retail Price", ""), [100])
        v.assert_all()


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - end to end")
class TestPaymentAndRecordList:

    @pytest.mark.parametrize("name,ratio", [("paid_in_full", 1.0), ("partial", 0.5), ("unpaid", 0.0)])
    @allure.story("Payment status, Total Paid and record-list row for full / partial / no payment (spec 44.1)")
    @pytest.mark.regression
    def test_payment_variants(self, flow, name, ratio):
        j, verifiers = journey(flow, Scenario(f"os-pay-{name}", CART_SHAPES["two_plain"]), paid_ratio=ratio)
        rec = InventoryRecordPage(flow.page).open()
        row = rec.row(0)
        v = Verifier(f"5. record list row [{name}]")
        v.contains("record list: Bill Amount shows the Final Price", rec.bill_amount_cell_text(row), f"{j.inventory.final_price:,.0f}")
        v.true("record list: Paid cell present", rec.paid_amount_cell_text(row) != "")
        v.true("record list: Status cell present", rec.status_cell_text(row) != "")
        if ratio == 1.0:
            v.contains("record list: status Paid", rec.status_cell_text(row), "Paid")
        else:
            v.contains("record list: status Due", rec.status_cell_text(row), "Due")
        verifiers.append(v)
        assert_journey(verifiers)

    @allure.story("Inventory Details Total Paid matches what was paid (BUG-INV-003 reconciliation)")
    @allure.issue("BUG-INV-003")
    @pytest.mark.regression
    def test_paid_in_full_is_fully_paid_in_record(self, flow):
        j, verifiers = journey(flow, Scenario("os-recon", CART_SHAPES["two_one_free"], discount=(10, "%")))
        d = j.details
        assert d.payment_status().strip().lower() == "paid"
        assert money(d.total_paid()) == pytest.approx(money(d.final_price()), abs=0.51)


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - end to end")
class TestCompletionSideEffects:

    @allure.story("Next Opening Stock entry of the same product preloads the saved retail / wholesale and re-derives BTP")
    @pytest.mark.regression
    def test_next_entry_preloads_latest_values(self, flow):
        spec = LineSpec("P0", box_qty=2, retail=77, wholesale=66)
        j = flow.fill_cart(Scenario("preload", (spec,)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        flow.complete_and_open_details(co, j)
        inv = flow.inventory.open("Opening Stock")
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.page.wait_for_timeout(600)
        snap = inv.form_snapshot()
        v = Verifier("preload after an Opening Stock purchase")
        v.eq("Retail Price/Box preloaded from the latest inventory", float(snap["retail_price"]), 77)
        v.eq("Wholesale Price/Box preloaded from the latest inventory", float(snap["wholesale_price"]), 66)
        v.eq("Opening Stock % back to the default 12", float(snap["opening_stock_percent"]), 12)
        v.eq("BTP+VAT/Box re-derived from the preloaded retail (77 x 0.88)", float(snap["price_per_box"]), 67.76, tol=0.0051)
        v.assert_all()


# ============================================================================ Due / Less / Advance & Buy
_BUY_CASES = [
    # id,                    shape,                    discount,      choice,          paid_ratio, paid_delta
    ("due_half",             "two_plain",              None,          "Due & Buy",     0.5,  None),
    ("due_unpaid",           "single_plain",           None,          "Due & Buy",     0.0,  None),
    ("due_pct10_free_line",  "two_one_free",           (10, "%"),     "Due & Buy",     0.4,  None),
    ("less_half",            "two_plain",              None,          "Less & Buy",    0.5,  None),
    ("less_flat50_mixed",    "three_plain_free_plain", (50, "Tk"),    "Less & Buy",    0.7,  None),
    ("advance_100",          "single_plain",           None,          "Advance & Buy", None, 100),
    ("advance_pct7_5",       "two_one_free",           (7.5, "%"),    "Advance & Buy", None, 250),
]


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - Due & Buy / Less & Buy / Advance & Buy")
class TestPaymentDecisionDialog:
    """Complete Inventory with Total Paid != Final Price opens a decision dialog. These tests only LOOK at it and
    dismiss it - nothing is created."""

    @pytest.mark.parametrize("ratio", [0.5, 0.0], ids=["paid_half", "paid_nothing"])
    @allure.story("Paid less than the bill: dialog offers 'Due & Buy' and 'Less & Buy' with the exact short amount")
    @pytest.mark.regression
    def test_dialog_when_paid_less(self, flow, ratio):
        j = flow.fill_cart(Scenario("os-dlg-less", CART_SHAPES["two_plain"]))
        final = flow.oracle(j).final_price
        co = flow.open_checkout(j)
        paid = round(final * ratio, 2)
        flow.pay(co, j, paid)
        dlg = co.complete_expecting_dialog()
        v = Verifier("payment dialog (paid less)")
        v.true("dialog opened", dlg.is_open(), "Complete Inventory showed no payment dialog")
        if dlg.is_open():
            check_payment_dialog(v, dlg.snapshot(), final, paid, j.supplier)
            v.true("Escape closes the dialog without choosing", dlg.dismiss(), "dialog still open")
            v.true("still on checkout - no inventory was created", co.is_loaded(), "left the checkout page")
        v.assert_all()

    @allure.story("Paid more than the bill: dialog offers only 'Advance & Buy' with the exact extra amount")
    @pytest.mark.regression
    def test_dialog_when_paid_more(self, flow):
        j = flow.fill_cart(Scenario("os-dlg-more", CART_SHAPES["single_plain"]))
        final = flow.oracle(j).final_price
        co = flow.open_checkout(j)
        paid = round(final + 100, 2)
        flow.pay(co, j, paid)
        dlg = co.complete_expecting_dialog()
        v = Verifier("payment dialog (paid more)")
        v.true("dialog opened", dlg.is_open(), "Complete Inventory showed no payment dialog")
        if dlg.is_open():
            check_payment_dialog(v, dlg.snapshot(), final, paid, j.supplier)
            v.true("Escape closes the dialog without choosing", dlg.dismiss(), "dialog still open")
            v.true("still on checkout - no inventory was created", co.is_loaded(), "left the checkout page")
        v.assert_all()


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - Due & Buy / Less & Buy / Advance & Buy")
class TestDueLessAdvanceBuy:
    """Full journeys that take each payment decision, then check the dialog, the Inventory Details of the created
    record and the supplier's balance on the Supplier List (workbook N2-N5; Less is deducted)."""

    @pytest.mark.parametrize("case", _BUY_CASES, ids=[c[0] for c in _BUY_CASES])
    @allure.story("Take Due & Buy / Less & Buy / Advance & Buy and verify details + supplier balance")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.regression
    def test_buy_decision_journey(self, flow, case):
        cid, shape, discount, choice, ratio, delta = case
        scenario = Scenario(f"os-buy-{cid}", CART_SHAPES[shape], discount=discount)
        j, verifiers = buy_journey(flow, scenario, choice=choice, paid_ratio=ratio, paid_delta=delta)
        assert_journey(verifiers)
