"""Default mode - END-TO-END: create form -> cart -> checkout -> Complete ->
Inventory Record -> Inventory Details (spec sections 42-44.1).

Each journey verifies EVERY stage against the oracle and then proves that the
record it just created is the one displayed in Inventory Details, line by
line (matched by the unique batch numbers entered). A mismatch at one stage
never hides a mismatch at another - all are reported together.

These tests create real inventories on the target environment.
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_checkout_page import InventoryCompleteModal
from pages.inventory_record_page import InventoryRecordPage
from pages.my_products_page import MyProductsPage
from tests.inventory.scenario_params import scenario_params
from tests.inventory.shared_journey import assert_journey, buy_journey, check_payment_dialog, journey
from utils.helpers import money
from utils.inventory_assertions import Verifier, check_details_free
from utils.inventory_scenarios import CART_SHAPES, LineSpec, Scenario, e2e_scenarios

pytestmark = [pytest.mark.inventory, pytest.mark.e2e]


@allure.epic("Inventory")
@allure.feature("Default mode - end to end")
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
@allure.feature("Default mode - end to end")
class TestDetailsContent:

    @allure.story("Details shows Free Qty in the Qty column as 'N pc free' and Total (+ Final) in the Price column (spec 44.1)")
    @pytest.mark.regression
    def test_details_shows_free_and_total(self, flow):
        j = flow.fill_cart(Scenario("free", (LineSpec("P0", box_qty=2, btp_vat_per_box=33.3, free_qty=3),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        row = dlg.item_row_by_batch(j.batches[0])
        v = Verifier("details free / total")
        check_details_free(v, row, 3, j.batches[0])
        v.contains("Price column shows 'Total:'", (row or {}).get("Price", ""), "Total")
        v.assert_all()

    @allure.story("Details exposes every required pricing field and item column (Min. Qty / Barcode not required)")
    @pytest.mark.regression
    def test_details_required_fields_and_columns(self, flow):
        j = flow.fill_cart(Scenario("cols", (LineSpec("P0", box_qty=1, btp_vat_per_box=20),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        dlg.wait_loaded()
        assert not dlg.missing_pricing_breakdown_fields(), dlg.missing_pricing_breakdown_fields()
        assert not dlg.missing_item_columns(), dlg.missing_item_columns()


@allure.epic("Inventory")
@allure.feature("Default mode - end to end")
class TestPaymentAndRecordList:

    @pytest.mark.parametrize("name,ratio", [("paid_in_full", 1.0), ("partial", 0.5), ("unpaid", 0.0)])
    @allure.story("Payment status, Total Paid and record-list row for full / partial / no payment (spec 44.1)")
    @pytest.mark.regression
    def test_payment_variants(self, flow, name, ratio):
        j, verifiers = journey(flow, Scenario(f"pay-{name}", CART_SHAPES["two_plain"]), paid_ratio=ratio)
        rec = InventoryRecordPage(flow.page).open()
        row = rec.row(0)
        v = Verifier(f"5. record list row [{name}]")
        v.contains("record list: Bill Amount shows the Final Price", rec.bill_amount_cell_text(row), f"{j.inventory.final_price:,.0f}")
        v.true("record list: Paid cell present", rec.paid_amount_cell_text(row) != "")
        v.true("record list: Status cell present", rec.status_cell_text(row) != "")
        if ratio == 1.0:
            v.contains("record list: status Paid", rec.status_cell_text(row), "Paid")
        else:
            own_due = j.inventory.final_price - j.paid
            v.contains("record list: status Due (BUG-INV-031)", rec.status_cell_text(row), "Due")
            v.any_number("record list: Due = this record's own Final - Paid, not netted against the supplier's advance (BUG-INV-031)",
                         rec.status_cell_text(row), [own_due], tol=0.51)
        verifiers.append(v)
        assert_journey(verifiers)

    @allure.story("Inventory Details Total Paid matches what was paid (BUG-INV-003 reconciliation)")
    @allure.issue("BUG-INV-003")
    @pytest.mark.regression
    def test_paid_in_full_is_fully_paid_in_record(self, flow):
        j, verifiers = journey(flow, Scenario("recon", CART_SHAPES["two_one_free"], discount=(10, "%")))
        d = j.details
        assert d.payment_status().strip().lower() == "paid"
        assert money(d.total_paid()) == pytest.approx(money(d.final_price()), abs=0.51)

    @allure.story("Overpayment is recorded as supplier Advance (spec 44.1)")
    @allure.issue("BUG-INV-016")
    @pytest.mark.regression
    def test_overpayment(self, flow):
        j = flow.fill_cart(Scenario("over", CART_SHAPES["single_plain"]))
        o = flow.oracle(j)
        co = flow.open_checkout(j)
        flow.pay(co, j, o.final_price + 100)
        dlg = flow.complete_and_open_details(co, j)
        assert money(dlg.total_paid()) == pytest.approx(o.final_price + 100, abs=0.51)


@allure.epic("Inventory")
@allure.feature("Default mode - end to end")
class TestCompletionSideEffects:

    @allure.story("BUG-INV-002: an 'Inventory Complete' modal shows the spec 42.1 fields and actions")
    @allure.issue("BUG-INV-002")
    @pytest.mark.regression
    def test_completion_modal(self, flow):
        j = flow.fill_cart(Scenario("modal", CART_SHAPES["single_plain"]))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        co.complete()
        modal = InventoryCompleteModal(flow.page)
        assert modal.wait_open(), "no 'Inventory Complete' modal after a successful completion (BUG-INV-002)"
        assert not modal.missing_fields(), f"modal missing fields: {modal.missing_fields()}"
        assert not modal.missing_actions(), f"modal missing actions: {modal.missing_actions()}"
        assert modal.has_details_link()

    @allure.story("Stock increases by purchased + free pieces after completion (spec 42, 44)")
    @pytest.mark.regression
    def test_stock_increase(self, flow, catalogue):
        mp = MyProductsPage(flow.page).open().wait_loaded()
        product = catalogue[1]
        mp.search(product)
        before = mp.available_qty(product)
        if before is None:
            pytest.skip("My Products exposes no numeric stock/qty column to read")
        flow.inventory.open("Default")
        j = flow.fill_cart(Scenario("stock", (LineSpec("P1", box_qty=3, btp_vat_per_box=21.6, free_qty=5),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        flow.complete_and_open_details(co, j)
        mp = MyProductsPage(flow.page).open().wait_loaded()
        mp.search(product)
        after = mp.available_qty(product)
        expected = j.lines[0].total_qty + j.lines[0].free_qty
        assert after - before == pytest.approx(expected), f"stock {before} -> {after}, expected +{expected} (incl. free)"

    @allure.story("Next inventory for the same product preloads the latest saved prices (spec 4, 21)")
    @pytest.mark.regression
    def test_next_inventory_preloads_latest_values(self, flow):
        spec = LineSpec("P0", box_qty=2, btp_vat_per_box=44.4, retail=77, wholesale=66)
        j = flow.fill_cart(Scenario("preload", (spec,)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        flow.complete_and_open_details(co, j)
        inv = flow.inventory.open("Default")
        inv.select_product(inv.resolve_product("P0"), exact=True)
        snap = inv.form_snapshot()
        v = Verifier("preload after purchase")
        v.eq("Retail Price/Box preloaded from latest inventory", float(snap["retail_price"]), 77)
        v.eq("Wholesale Price/Box preloaded from latest inventory", float(snap["wholesale_price"]), 66)
        v.eq("BTP+VAT/Box preloaded from latest inventory", float(snap["price_per_box"]), 44.4)
        v.assert_all()

    @allure.story("Borrow inventory must NOT become the product's reference record (spec: Borrow behaviour)")
    @pytest.mark.regression
    def test_borrow_does_not_update_reference_values(self, flow):
        base = LineSpec("P0", box_qty=1, btp_vat_per_box=10, retail=20, wholesale=15)
        j = flow.fill_cart(Scenario("base", (base,)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        flow.complete_and_open_details(co, j)

        inv = flow.inventory.open("Default")
        borrow = LineSpec("P0", box_qty=1, btp_vat_per_box=999, retail=1999, wholesale=1555)
        jb = flow.fill_cart(Scenario("borrow", (borrow,), inventory_type="Borrow"))
        cob = flow.open_checkout(jb)
        flow.pay(cob, jb, flow.oracle(jb).final_price)
        flow.complete_and_open_details(cob, jb)

        inv = flow.inventory.open("Default")
        inv.select_product(inv.resolve_product("P0"), exact=True)
        snap = inv.form_snapshot()
        v = Verifier("borrow does not alter reference values")
        v.eq("BTP+VAT/Box still from the Purchase inventory", float(snap["price_per_box"]), 10)
        v.eq("Retail still from the Purchase inventory", float(snap["retail_price"]), 20)
        v.eq("Wholesale still from the Purchase inventory", float(snap["wholesale_price"]), 15)
        v.assert_all()

    @allure.story("BUG-INV-012: double-clicking Complete Inventory must create exactly one inventory")
    @allure.issue("BUG-INV-012")
    @pytest.mark.negative
    def test_double_click_creates_one_inventory(self, flow):
        j = flow.fill_cart(Scenario("dbl", CART_SHAPES["single_plain"]))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        statuses = co.complete_double_click()
        assert len([s for s in statuses if s < 400]) == 1, f"create responses: {statuses}"

    @allure.story("BUG-INV-011/020: a rejected Complete Inventory must tell the user why")
    @allure.issue("BUG-INV-020")
    @pytest.mark.negative
    def test_flat_discount_completion_is_not_silent(self, flow):
        j = flow.fill_cart(Scenario("flat", CART_SHAPES["two_plain"], discount=(50, "Tk")))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        status, body = co.complete_capturing_response()
        assert status is not None and status < 400, f"Flat discount completion rejected by the backend: {status} {body[:200]}"


# ============================================================================ Due / Less / Advance & Buy
_BUY_CASES = [
    # id,                    shape,                    discount,      choice,          paid_ratio, paid_delta
    ("due_half",             "two_plain",              None,          "Due & Buy",     0.5,  None),
    ("due_unpaid",           "two_plain",              None,          "Due & Buy",     0.0,  None),
    ("due_pct10_free_line",  "two_one_free",           (10, "%"),     "Due & Buy",     0.4,  None),
    ("less_half",            "two_plain",              None,          "Less & Buy",    0.5,  None),
    ("less_unpaid_full",     "single_plain",           None,          "Less & Buy",    0.0,  None),
    ("less_flat50_mixed",    "three_plain_free_plain", (50, "Tk"),    "Less & Buy",    0.7,  None),
    ("less_pct7_5_small",    "two_plain",              (7.5, "%"),    "Less & Buy",    0.9,  None),
    ("advance_100",          "single_plain",           None,          "Advance & Buy", None, 100),
    ("advance_pct7_5",       "two_one_free",           (7.5, "%"),    "Advance & Buy", None, 250),
    ("advance_fraction_rounds", "single_plain",        None,          "Advance & Buy", None, 0.5),
]


@allure.epic("Inventory")
@allure.feature("Default mode - Due & Buy / Less & Buy / Advance & Buy")
class TestPaymentDecisionDialog:
    """Complete Inventory with Total Paid != Final Price opens a decision dialog. These tests only LOOK at it
    and dismiss it - nothing is created."""

    @pytest.mark.parametrize("ratio", [0.5, 0.0], ids=["paid_half", "paid_nothing"])
    @allure.story("Paid less than the bill: dialog offers 'Due & Buy' and 'Less & Buy' with the exact short amount")
    @pytest.mark.regression
    def test_dialog_when_paid_less(self, flow, ratio):
        j = flow.fill_cart(Scenario("dlg-less", CART_SHAPES["two_plain"]))
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
        j = flow.fill_cart(Scenario("dlg-more", CART_SHAPES["single_plain"]))
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
@allure.feature("Default mode - Due & Buy / Less & Buy / Advance & Buy")
class TestDueLessAdvanceBuy:
    """Full journeys that take each payment decision, then check the dialog, the Inventory Details of the
    created record and the supplier's balance on the Supplier List (workbook M2-M5)."""

    @pytest.mark.parametrize("case", _BUY_CASES, ids=[c[0] for c in _BUY_CASES])
    @allure.story("Take Due & Buy / Less & Buy / Advance & Buy and verify details + supplier balance")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.regression
    def test_buy_decision_journey(self, flow, case):
        cid, shape, discount, choice, ratio, delta = case
        scenario = Scenario(f"buy-{cid}", CART_SHAPES[shape], discount=discount)
        j, verifiers = buy_journey(flow, scenario, choice=choice, paid_ratio=ratio, paid_delta=delta)
        assert_journey(verifiers)
