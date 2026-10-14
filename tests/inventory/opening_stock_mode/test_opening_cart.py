"""Opening Stock mode - Inventory Cart (spec sections 27-34).

Every cart shape from utils.opening_scenarios.CART_SHAPES is entered through the create form (Retail Price/Box,
Opening Stock %, or a manual BTP+VAT/Box) and the cart is verified row by row against the oracle. The oracle line is
built from the values the FORM held after entry and ALSO compared with the independent derivation
``utils.opening_calc.btp_for``, so a wrong derivation cannot hide behind read-back values.
Nothing here completes an inventory.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.shared_cart import CartContentsCases, SpecialLineCartCases
from utils.inventory_assertions import Verifier, check_cart
from utils.inventory_scenarios import LineSpec, Scenario
from utils.opening_calc import DEFAULT_PCT, btp_for
from utils.opening_scenarios import CART_SHAPES

pytestmark = [pytest.mark.inventory, pytest.mark.regression]


def _expected_btp(spec: LineSpec, form_retail: float) -> float:
    if spec.btp_vat_per_box is not None:
        return spec.btp_vat_per_box
    retail = spec.retail if spec.retail is not None else form_retail
    return btp_for(retail, spec.opening_pct if spec.opening_pct is not None else DEFAULT_PCT)


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - cart")
class TestCartContents(CartContentsCases, SpecialLineCartCases):
    SHAPES = CART_SHAPES
    HEADERS = ("Details", "Box Qty", "BTP+VAT/Box", "Discount", "Total Price", "Exp date", "Free", "Action")
    ABSENT_HEADERS = ("TP/Box", "VAT/Box")
    VERIFIER = Verifier
    CHECK_CART = staticmethod(check_cart)

    def _check_shape(self, v, j) -> None:
        for spec, line in zip(j.specs, j.lines):
            v.eq(f"derivation [{line.name}]: BTP+VAT/Box = Retail x (1 - %)", line.btp_vat_per_box,
                 _expected_btp(spec, line.retail_per_box), tol=0.0051)

    @allure.story("Cart Total Price = sum of line totals; free pieces add nothing")
    def test_cart_total(self, flow):
        j = flow.fill_cart(self._scenario("two_one_free"))
        assert flow.inventory.cart_total_price() == pytest.approx(sum(l.total_btp_vat for l in j.lines))

    @allure.story("Edit Cart Item re-opens the line with its retail and BTP+VAT/Box as entered")
    def test_edit_keeps_manual_btp(self, flow):
        inv = flow.inventory
        j = flow.fill_cart(Scenario("edit", (LineSpec("P1", box_qty=2, retail=100, btp_vat_per_box=70),)))
        inv.edit_cart_row(inv.cart_row(0))
        shown = float((inv.value_of("price_per_box") or "0").replace(",", ""))
        retail = float((inv.value_of("retail_price") or "0").replace(",", ""))
        assert retail == 100 and shown == 70, f"edit form shows retail {retail:g} / BTP+VAT/Box {shown:g}, expected 100 / 70"
