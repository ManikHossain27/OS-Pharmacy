"""TP/VAT mode - Inventory Cart (spec sections 27-34).

Every cart shape from utils.tpvat_scenarios.CART_SHAPES is entered through the create form and the cart is
verified row by row against the oracle (utils.tpvat_calc). Nothing here completes an inventory.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.shared_cart import CartContentsCases, SpecialLineCartCases
from utils.tpvat_assertions import Verifier, check_cart
from utils.tpvat_scenarios import CART_SHAPES

pytestmark = [pytest.mark.inventory, pytest.mark.regression]


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - cart")
class TestCartContents(CartContentsCases, SpecialLineCartCases):
    SHAPES = CART_SHAPES
    HEADERS = ("Details", "Box Qty", "TP/Box", "VAT/Box", "Discount", "Total Price", "Exp date", "Free", "Action")
    ABSENT_HEADERS = ("BTP+VAT",)
    VERIFIER = Verifier
    CHECK_CART = staticmethod(check_cart)

    @allure.story("Cart Total Price = sum of line totals, including VAT carried by free pieces")
    def test_cart_total_includes_free_vat(self, flow):
        j = flow.fill_cart(self._scenario("two_one_free"))
        assert flow.inventory.cart_total_price() == pytest.approx(sum(l.total_price for l in j.lines))
