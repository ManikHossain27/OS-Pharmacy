"""Regression tests for the remaining High Sale bugs of 2026-10-27 (docs/SALE_MANAGEMENT.md): BUG-SALE-030 expired batch,
BUG-SALE-034 cashier discount, BUG-SALE-008 walk-in overpayment.

Each test asserts the CORRECT behaviour, so it fails while the bug exists and carries ``allure.issue``. The sales are real
(1-2 pieces) and show up in Sale Record.
"""
from __future__ import annotations

import allure
import pytest

from tests.sale.conftest import EXPIRED_PRODUCT, PRODUCT

pytestmark = [pytest.mark.sale, pytest.mark.regression]

PRICE = 50


def _term(name: str) -> str:
    return name.lower()


@allure.epic("Sale")
@allure.feature("Sale - High severity regressions")
class TestHighBugs:

    @allure.story("BUG-SALE-030: an expired batch is skipped, blocked or at least warned about - never sold silently")
    @allure.issue("BUG-SALE-030")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_expired_batch_is_not_sold_silently(self, sale, checkout, default_config):
        if not sale.product_options(_term(EXPIRED_PRODUCT)):
            pytest.skip(f"expired product {EXPIRED_PRODUCT!r} not found - set QA_EXPIRED_PRODUCT")
        sale.add_line(_term(EXPIRED_PRODUCT), 1, named=EXPIRED_PRODUCT)
        seen = [sale.page.locator("main").inner_text()]                       # cart
        sale.go_to_checkout()
        seen.append(sale.page.locator("main").inner_text())                   # checkout
        status, body = checkout.complete_once()
        seen += [checkout.toast(), body]
        warned = any("expir" in text.lower() for text in seen)
        blocked = status is None or status >= 400
        assert blocked or warned, (
            f"1 piece of {EXPIRED_PRODUCT} (expired stock) was sold (status {status}) with no expiry warning anywhere")

    @allure.story("BUG-SALE-034: a discount typed by the cashier is applied when the queued sale is approved")
    @allure.issue("BUG-SALE-034")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cashier_discount_is_applied_on_approval(self, sale, checkout, cashier, sale_record, sale_config):
        sale_config.apply({"separateCashier": True})
        if cashier.open().queue_count():
            pytest.skip("the Cashier queue is not empty - approve or clear it first (the queue search does not work, BUG-SALE-018)")
        sale.open()
        sale.add_line(_term(PRODUCT), 2, price=PRICE, named=PRODUCT)          # Tk 100
        sale.go_to_checkout()
        status, body = checkout.complete_once()
        assert status is not None and status < 300, f"sending the sale to the cashier failed: {status} {body[:200]}"

        assert cashier.open().queue_count() == 1, "the sent sale should be the only one in the queue"
        cashier.set_discount(10)                                              # panel shows Final Price Tk 90
        toast = cashier.complete()
        assert "checked out" in toast.lower(), f"approval failed: {toast!r}"

        top = sale_record.open().top_row()
        assert top.bill == pytest.approx(90.0), f"the 10% cashier discount was not saved: Sale Record bill Tk {top.bill} ({top.raw})"

    @allure.story("BUG-SALE-008: a walk-in overpayment settled as 'Profit & Sale' is not recorded as an Advance")
    @allure.issue("BUG-SALE-008")
    def test_walk_in_overpayment_is_not_an_advance(self, sale, checkout, sale_record, default_config):
        sale.add_line(_term(PRODUCT), 1, price=PRICE, named=PRODUCT)          # Tk 50
        sale.go_to_checkout()
        checkout.set_paid(80)
        status, _ = checkout.complete_once()
        assert status is None, "paying more than the bill should open the Excess Payment dialog, not complete the sale"
        status, body = checkout.settle("Profit & Sale")
        assert status is not None and status < 300, f"settling failed: {status} {body[:200]}"

        top = sale_record.open().top_row()
        assert top.customer.lower().startswith("walk"), f"expected the walk-in sale at the top: {top.raw}"
        assert top.status != "Advance", f"a walk-in cannot hold an advance, but the sale was saved as {top.status!r} ({top.raw})"
