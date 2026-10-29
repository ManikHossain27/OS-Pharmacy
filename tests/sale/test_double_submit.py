"""Double-submit regression tests: a rapid double click on any button that posts money or creates a record must send ONE request.

Found 2026-10-27/28 (docs/SALE_MANAGEMENT.md): Complete Sale (BUG-SALE-022, tested in test_sale_checkout_regression.py),
Confirm New Payment (BUG-SALE-055), Hold Current Sale (BUG-SALE-056), Confirm New Customer and Complete Sale Return
(BUG-SALE-057: two requests, the server rejects the second and the UI shows an error toast although the first succeeded).
Cancel Sale already behaves (one request) and is kept as a guard.

Each test asserts the CORRECT behaviour, so it fails while the bug exists. The sales, customers and payments they create are
real (a few pieces / Tk 5); customer names carry the run tag.
"""
from __future__ import annotations

import allure
import pytest

from pages.customer_page import unique_phone
from tests.sale.conftest import PRODUCT

pytestmark = [pytest.mark.sale, pytest.mark.regression, pytest.mark.negative]

PRICE = 50


def _term(name: str) -> str:
    return name.lower()


def _sell(sale, checkout, qty: int):
    sale.open()
    sale.add_line(_term(PRODUCT), qty, price=PRICE, named=PRODUCT)
    sale.go_to_checkout()
    status, body = checkout.complete_once()
    assert status is not None and status < 300, f"set-up sale failed: {status} {body[:200]}"


@allure.epic("Sale")
@allure.feature("Double submit")
class TestDoubleSubmit:

    @allure.story("BUG-SALE-055: double-clicking Confirm New Payment records one payment")
    @allure.issue("BUG-SALE-055")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_customer_payment_double_click_records_one_payment(self, customers, run_tag):
        name = f"QA DS Pay {run_tag}"
        customers.open().create(name, balance=100, balance_type="Due")
        customers.open().search(name)
        assert customers.balance(name) == pytest.approx(100.0), "set-up: the new customer should owe Tk 100"

        customers.open_payment_form(name).fill_payment(5)
        statuses = customers.confirm_payment_double_click()
        assert len(statuses) == 1, f"{len(statuses)} payment requests for one double click: {statuses}"

        customers.open().search(name)
        assert customers.balance(name) == pytest.approx(95.0), "a Tk 5 payment must reduce the Due by Tk 5 once"

    @allure.story("BUG-SALE-056: double-clicking Hold Current Sale creates one hold")
    @allure.issue("BUG-SALE-056")
    def test_hold_double_click_creates_one_hold(self, sale, default_config):
        before = sale.hold_count()
        sale.add_line(_term(PRODUCT), 1, price=PRICE, named=PRODUCT)
        try:
            after = sale.hold_double_click()
            assert after - before == 1, f"holds went from {before} to {after} for one cart"
        finally:
            if before == 0:
                sale.page.reload()
                sale.clear_holds()

    @allure.story("BUG-SALE-057: double-clicking Confirm New Customer sends one create request")
    @allure.issue("BUG-SALE-057")
    def test_add_customer_double_click_sends_one_request(self, customers, run_tag):
        customers.open().open_add_form().fill_add_form(f"QA DS Cust {run_tag}", unique_phone())
        sent = customers.confirm_add_double_click()
        assert sent == 1, f"{sent} create requests for one double click (the second is rejected as a duplicate phone)"

    @allure.story("BUG-SALE-057: double-clicking Complete Sale Return sends one return request")
    @allure.issue("BUG-SALE-057")
    def test_return_double_click_sends_one_request(self, sale, checkout, sale_record, sale_return, default_config):
        _sell(sale, checkout, 2)
        sale_return.open_from_record(sale_record.open(), 0)
        sale_return.set_return_qty(0, 1).go_to_return_checkout()
        statuses = sale_return.complete_double_click()
        assert len(statuses) == 1, f"{len(statuses)} return requests for one double click: {statuses}"

    @allure.story("Guard: double-clicking 'Yes, cancel it' cancels once")
    def test_cancel_sale_double_click_cancels_once(self, sale, checkout, sale_record, default_config):
        _sell(sale, checkout, 1)
        sale_record.open().open_row_action(0, "Cancel Sale")
        sent = sale_record.confirm_cancel_double_click()
        assert sent == 1, f"{sent} cancel requests for one double click"
