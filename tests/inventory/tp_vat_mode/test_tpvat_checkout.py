"""TP/VAT mode - Inventory Checkout (spec sections 35-41).

Cart shape x discount (40 combinations) is verified against the oracle WITHOUT completing the inventory,
so this module creates no stock or financial data.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.scenario_params import scenario_params
from tests.inventory.shared_checkout import CheckoutBehaviourCases
from utils.tpvat_assertions import Verifier, check_checkout_rows, check_checkout_summary
from utils.tpvat_calc import build
from utils.tpvat_scenarios import CART_SHAPES, e2e_scenarios

pytestmark = [pytest.mark.inventory, pytest.mark.regression]


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - checkout")
class TestCheckoutMatrix:

    @pytest.mark.parametrize("scenario", scenario_params(e2e_scenarios()))
    @allure.story("Checkout Total / TP / VAT / Discount (on TP) / Final Price and item rows match the oracle for every cart x discount")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_checkout_summary_matches_oracle(self, flow, scenario):
        for bug in scenario.known_bugs:
            allure.dynamic.issue(bug)
        j = flow.fill_cart(scenario)
        inv = flow.oracle(j)
        co = flow.open_checkout(j)
        inv = flow.oracle(j)             # re-evaluate: the discount may have been blocked (input disabled)
        v = Verifier(f"checkout [{scenario.id}]")
        check_checkout_rows(v, co.cart_rows(), j.lines)
        check_checkout_summary(v, co.tpvat_totals(), inv, paid=inv.final_price)   # app pre-fills Total Paid = Final Price
        v.assert_all()


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - checkout")
class TestCheckoutBehaviour(CheckoutBehaviourCases):
    MODE = "TP/VAT"
    SHAPES = CART_SHAPES
    build = staticmethod(build)
    SUMMARY_LABELS = ("Total Price (TP+VAT)", "Total TP", "Total VAT", "General Discount (on TP)", "Special Discount",
                      "Round Off", "Final Price", "Total Paid", "Due")

    @staticmethod
    def _totals(co) -> dict:
        return co.tpvat_totals()

    def _check_percentage_side_effects(self, oracle, totals) -> None:
        assert totals["total_vat"] == pytest.approx(oracle.total_vat, abs=0.011), "VAT must not be reduced by the discount"

    @allure.story("The discount control is labelled 'Discount (on TP)' - the discount basis is TP only (spec 38)")
    def test_discount_label_states_tp_basis(self, flow):
        j, co = self._open(flow, "two_plain")
        assert co.page.get_by_text("Discount (on TP)", exact=True).count() >= 1

    @allure.story("Total TP + Total VAT = Total Price")
    def test_tp_plus_vat_equals_total(self, flow):
        j, co = self._open(flow, "three_plain_free_plain")
        s = co.tpvat_totals()
        assert s["total_tp"] + s["total_vat"] == pytest.approx(s["total_price"], abs=0.011)

    @allure.story("A Special Discount line is excluded from the General Discount and listed under Special Discount")
    def test_special_line_split(self, flow):
        j, co = self._open(flow, "special_line_with_plain", (10, "%"))
        o = build(j.lines, pct=10)
        s = co.tpvat_totals()
        assert s["special_discount"] == pytest.approx(o.sum_special_applied, abs=0.011)
        assert s["discount_amount"] == pytest.approx(o.general_discount, abs=0.011)
