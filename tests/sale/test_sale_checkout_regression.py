"""Regression tests for the High / Medium Sale bugs found on 2026-10-27 (docs/SALE_MANAGEMENT.md, BUG-SALE-0xx).

Each test asserts the CORRECT behaviour, so it fails while the bug exists (the repo's convention: ``allure.issue`` names the bug)
and turns green when it is fixed. Sales completed here are real; they sell 1-2 pieces of the configured product.
"""
from __future__ import annotations

import json

import allure
import pytest

from tests.sale.conftest import PRODUCT, PRODUCT_2, PRODUCT_2_PRICE

pytestmark = [pytest.mark.sale, pytest.mark.regression]

PRICE = 50          # typed per-piece sale price; well above the product's batch cost
TOL = 0.005


def _term(name: str) -> str:
    return name.lower()


@allure.epic("Sale")
@allure.feature("Sale Checkout")
class TestCheckoutRegression:

    @allure.story("BUG-SALE-037: the overall discount excludes line-discounted items (SRS)")
    @allure.issue("BUG-SALE-037")
    def test_overall_discount_excludes_line_discounted_items(self, sale, checkout, default_config):
        if not sale.product_options(_term(PRODUCT_2)):
            pytest.skip(f"second product {PRODUCT_2!r} not found - set QA_SALE_PRODUCT_2")
        sale.add_line(_term(PRODUCT_2), 2, price=PRODUCT_2_PRICE)                       # no line discount: base 70
        sale.add_line(_term(PRODUCT), 2, price=PRICE, discount_pct=10, named=PRODUCT)   # line discount: excluded
        sale.go_to_checkout()
        checkout.set_overall_discount(10)
        s = checkout.summary()
        expected = round(0.10 * 2 * PRODUCT_2_PRICE, 2)
        assert abs(s["Discount Amount"] - expected) < TOL, (
            f"overall 10% must apply only to the Tk {2 * PRODUCT_2_PRICE} line without a line discount "
            f"(expected Tk {expected}), summary={s}")

    @allure.story("BUG-SALE-022: double-clicking Complete Sale creates one sale")
    @allure.issue("BUG-SALE-022")
    def test_double_click_complete_creates_one_sale(self, sale, checkout, default_config):
        sale.add_line(_term(PRODUCT), 1, price=PRICE, named=PRODUCT)
        sale.go_to_checkout()
        statuses = checkout.complete_double_click()
        created = [s for s in statuses if s < 300]
        assert len(created) == 1, f"{len(created)} sales created by one double click: {statuses}"

    @allure.story("BUG-SALE-023: Allow Loss Sale OFF also blocks a net price below cost reached through a line discount")
    @allure.issue("BUG-SALE-023")
    def test_line_discount_cannot_take_price_below_cost(self, sale, checkout, default_config):
        # control: a plain below-cost price (4.50 vs a batch cost of about 7) is blocked at checkout
        sale.add_line(_term(PRODUCT), 1, price=4.5, named=PRODUCT)
        sale.go_to_checkout()
        status, body = checkout.complete_once()
        if status is not None and status < 300:
            pytest.skip("control sale at Tk 4.50 was accepted - the product's cost is below that or Allow Loss Sale is ON")
        assert status == 400 and "below cost" in body.lower(), f"control not blocked as expected: {status} {body[:200]}"
        # the same net price (5 less 10% = 4.50) through a line discount must be blocked as well
        sale.open()
        sale.add_line(_term(PRODUCT), 1, price=5, discount_pct=10, named=PRODUCT)
        sale.go_to_checkout()
        status, body = checkout.complete_once()
        assert status == 400, f"a line discount bypassed the loss-sale rule: {status} {body[:200]}"

    @allure.story("BUG-SALE-040: the server rejects a walk-in shortfall that carries no settlement choice")
    @allure.issue("BUG-SALE-040")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_server_rejects_walk_in_shortfall_without_settlement(self, sale, checkout, default_config):
        sale.add_line(_term(PRODUCT), 1, price=PRICE, named=PRODUCT)
        sale.go_to_checkout()

        def short_pay(route):
            body = json.loads(route.request.post_data)
            assert body.get("settlementType") in (None, ""), "the test expects no settlement choice in the request"
            body["payments"][0]["amount"] = 1                       # pay Tk 1 of Tk 50, as a walk-in, with no settlement
            route.continue_(post_data=json.dumps(body))

        sale.page.route("**/sales/create/**", short_pay)
        try:
            status, body = checkout.complete_once()
        finally:
            sale.page.unroute("**/sales/create/**")
        assert status is not None and status >= 400, (
            f"a walk-in sale paid Tk 1 of Tk {PRICE} was created (status {status}) - it would carry a Due: {body[:200]}")
