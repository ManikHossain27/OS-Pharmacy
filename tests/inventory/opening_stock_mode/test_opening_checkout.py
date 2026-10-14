"""Opening Stock mode - Inventory Checkout (spec sections 35-41).

Cart shape x discount (40 combinations) is verified against the oracle WITHOUT completing the inventory, so this
module creates no stock or financial data. The discount base in this mode is BTP + VAT (spec 38 table), the same
as Default mode: percentage and Flat discounts are spread over the BTP+VAT of the eligible lines.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.scenario_params import scenario_params
from tests.inventory.shared_checkout import CheckoutBehaviourCases
from utils.inventory_assertions import Verifier, check_checkout_rows, check_checkout_summary
from utils.inventory_calc import build
from utils.opening_scenarios import CART_SHAPES, e2e_scenarios

pytestmark = [pytest.mark.inventory, pytest.mark.regression]


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - checkout")
class TestCheckoutMatrix:

    @pytest.mark.parametrize("scenario", scenario_params(e2e_scenarios()))
    @allure.story("Checkout Total / Discount / Special / Round Off / Final Price and item rows match the oracle for every cart x discount")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_checkout_summary_matches_oracle(self, flow, scenario):
        for bug in scenario.known_bugs:
            allure.dynamic.issue(bug)
        j = flow.fill_cart(scenario)
        co = flow.open_checkout(j)
        inv = flow.oracle(j)             # evaluated after open_checkout: the discount may have been blocked (input disabled)
        v = Verifier(f"checkout [{scenario.id}]")
        check_checkout_rows(v, co.cart_rows(), j.lines)
        check_checkout_summary(v, co.summary(), inv, paid=inv.final_price)   # the app pre-fills Total Paid = Final Price
        v.assert_all()


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - checkout")
class TestCheckoutBehaviour(CheckoutBehaviourCases):
    MODE = "Opening Stock"
    SHAPES = CART_SHAPES
    build = staticmethod(build)

    @allure.story("Opening Stock checkout has no TP / VAT split lines")
    def test_no_tp_vat_split(self, flow):
        j, co = self._open(flow, "two_plain")
        for label in ("Total TP", "Total VAT", "General Discount (on TP)"):
            assert co.summary_root.get_by_text(label, exact=True).count() == 0, f"{label!r} must not appear in Opening Stock mode"

    @allure.story("A Special Discount line is excluded from the General Discount and listed under Special Discount")
    def test_special_line_split(self, flow):
        j, co = self._open(flow, "special_line_with_plain", (10, "%"))
        o = build(j.lines, pct=10)
        s = co.summary()
        sp = sum(l.discount_value for l in o.lines if l.special_discount > 0)
        assert s["special_discount"] == pytest.approx(sp, abs=0.011)
        assert s["discount_amount"] == pytest.approx(o.total_discount - sp, abs=0.011)
