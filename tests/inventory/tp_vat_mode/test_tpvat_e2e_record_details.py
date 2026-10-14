"""TP/VAT mode - END-TO-END: create form -> cart -> checkout -> Complete -> Inventory Record -> Inventory Details.

Each journey verifies EVERY stage against the oracle (utils.tpvat_calc, validated against the sheet
'TP per vat mode (2)') and then proves that the record it just created is the one displayed in Inventory
Details, line by line (matched by the unique batch numbers entered).

These tests create real inventories on the target environment.
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.scenario_params import scenario_params
from tests.inventory.shared_journey import assert_journey, buy_journey, journey
from utils.inventory_scenarios import LineSpec, Scenario
from utils.tpvat_assertions import Verifier, check_details_free
from utils.tpvat_scenarios import CART_SHAPES, e2e_scenarios

pytestmark = [pytest.mark.inventory, pytest.mark.e2e]


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - end to end")
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
@allure.feature("TP/VAT mode - end to end")
class TestDetailsContent:

    @allure.story("Details of a TP/VAT record: mode 'TP/VAT', Total TP / Total VAT rows, TP and VAT item columns (spec 44.1)")
    @pytest.mark.regression
    def test_details_shows_tp_vat_structure(self, flow):
        j = flow.fill_cart(Scenario("cols", (LineSpec("P0", box_qty=1, tp_per_box=20),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        dlg.wait_loaded()
        fields = dlg.pricing_breakdown()
        assert fields.get("Inventory Mode", "").strip() == "TP/VAT"
        for label in ("Total TP", "Total VAT", "General Discount (on TP)", "Special Discount", "Final Price", "Payment Status"):
            assert label in fields, f"Details is missing {label!r}; got {list(fields)}"
        headers = dlg.item_headers()
        for col in ("Details", "Batch / Expiry", "Rack No", "Qty", "Qty/Box", "TP", "VAT", "Discount", "Purchase Price",
                    "Retail Price", "Wholesale Price", "Margin", "Price"):
            assert col in headers, f"item column {col!r} missing; got {headers}"
        assert "BTP+VAT" not in headers

    @allure.story("Free Qty shows as 'N pc free' in Qty and VAT is charged on free pieces: (15+10)x2 + 1.00x10 = 60; 60/30 = 2.00/pc")
    @pytest.mark.regression
    def test_free_qty_total_and_purchase_price(self, flow):
        j = flow.fill_cart(Scenario("free", (LineSpec("P0", box_qty=2, tp_per_box=15, vat_per_box=10, free_qty=10),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        row = dlg.item_row_by_batch(j.batches[0])
        v = Verifier("details free")
        check_details_free(v, row, 10, j.batches[0])
        v.any_number("Price column Total = 60", (row or {}).get("Price", ""), [60])
        v.any_number("Purchase Price = 2.00 per piece / 20.00 per box", (row or {}).get("Purchase Price", ""), [2.0, 20.0])
        v.assert_all()

    @allure.story("Special Discount line: Details shows SP.Dis and the Special Discount total")
    @pytest.mark.regression
    def test_special_discount_in_details(self, flow):
        j = flow.fill_cart(Scenario("sp", (LineSpec("P0", box_qty=2, tp_per_box=100, special=20),)))
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        fields = dlg.pricing_breakdown()
        row = dlg.item_row_by_batch(j.batches[0])
        v = Verifier("details special")
        v.any_number("Special Discount total = 20", fields.get("Special Discount", ""), [20])
        v.contains("Discount cell shows SP.Dis", (row or {}).get("Discount", ""), "SP.Dis")
        v.any_number("Final Price = ROUND(234.80 - 20) = 215", fields.get("Final Price", ""), [215])
        v.assert_all()


_BUY_CASES = [
    # id,                shape,                    discount,    choice,          paid_ratio, paid_delta
    ("due_half",         "two_plain",              None,        "Due & Buy",     0.5,  None),
    ("due_unpaid_free",  "two_one_free",           (10, "%"),   "Due & Buy",     0.0,  None),
    ("less_half",        "two_plain",              None,        "Less & Buy",    0.5,  None),
    ("less_flat_mixed",  "three_plain_free_plain", (50, "Tk"),  "Less & Buy",    0.7,  None),
    ("advance_100",      "single_plain",           None,        "Advance & Buy", None, 100),
    ("advance_special",  "special_line_with_plain", (7.5, "%"), "Advance & Buy", None, 250),
]


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - Due & Buy / Less & Buy / Advance & Buy")
class TestDueLessAdvanceBuy:

    @pytest.mark.parametrize("case", _BUY_CASES, ids=[c[0] for c in _BUY_CASES])
    @allure.story("Take Due & Buy / Less & Buy / Advance & Buy in TP/VAT mode and verify details + supplier balance")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.regression
    def test_buy_decision_journey(self, flow, case):
        cid, shape, discount, choice, ratio, delta = case
        scenario = Scenario(f"tvbuy-{cid}", CART_SHAPES[shape], discount=discount)
        j, verifiers = buy_journey(flow, scenario, choice=choice, paid_ratio=ratio, paid_delta=delta)
        assert_journey(verifiers)


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - end to end")
class TestPaymentAndRecordList:

    @pytest.mark.parametrize("name,ratio", [("paid_in_full", 1.0), ("unpaid", 0.0)])
    @allure.story("Record-list row (Bill, Paid, Status) for full / no payment (spec 44.1)")
    @pytest.mark.regression
    def test_record_list_row(self, flow, name, ratio):
        scenario = Scenario(f"tvpay-{name}", CART_SHAPES["two_plain"])
        j, verifiers = journey(flow, scenario, paid_ratio=ratio)
        rec = InventoryRecordPage(flow.page).open()
        row = rec.row(0)
        v = Verifier(f"5. record list row [{name}]")
        v.contains("record list: Bill Amount shows the Final Price", rec.bill_amount_cell_text(row), f"{j.inventory.final_price:,.0f}")
        if ratio == 1.0:
            v.contains("record list: status Paid", rec.status_cell_text(row), "Paid")
        else:
            v.contains("record list: status Due", rec.status_cell_text(row), "Due")
        verifiers.append(v)
        assert_journey(verifiers)
