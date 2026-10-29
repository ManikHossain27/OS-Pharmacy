"""Customer flows (SRS 3.1 / 3.2): create + validation, duplicate phone, balances, payments, bad-debt, checkout hand-off, search, edit.

Every test creates its own customer (name carries the run tag, phone is unique) so tests are independent. Tests assert the
CORRECT behaviour; the ones that fail today carry ``allure.issue``.
"""
from __future__ import annotations

import re

import allure
import pytest

from pages.customer_page import unique_phone
from tests.sale.helpers import term
from tests.sale.conftest import PRODUCT

pytestmark = [pytest.mark.sale, pytest.mark.regression]


def _digits_sent(body: str) -> str:
    m = re.search(r'"phoneNumber"\s*:\s*"\+?880(\d+)"', body or "")
    return m.group(1) if m else ""


@allure.epic("Sale")
@allure.feature("Customer")
class TestCustomerCreate:

    @allure.story("TC-SALE-CU-03: a customer with only name and phone is created with balance 0")
    def test_minimum_customer_appears_in_list(self, customers, run_tag):
        name = f"QA CU Min {run_tag}"
        customers.open().create(name)
        customers.open().search(name)
        assert customers.row(name).count() == 1
        assert customers.balance(name) == 0

    @allure.story("TC-SALE-CU-05: name and phone are required (no request is sent)")
    def test_required_fields_block_submit(self, customers):
        customers.open().open_add_form().fill_add_form("", "")
        status, _, text = customers.submit_add_form()
        assert status is None, "an empty form was sent to the server"
        assert "required" in text.lower(), f"no required-field message: {text!r}"

    @allure.story("TC-SALE-CU-07: a duplicate phone is rejected, also when typed with a leading 0")
    def test_duplicate_phone_is_rejected(self, customers, run_tag):
        phone = customers.open().create(f"QA CU Dup A {run_tag}")
        for variant in (phone, "0" + phone):
            customers.open().open_add_form().fill_add_form(f"QA CU Dup B {run_tag}", variant)
            status, _, text = customers.submit_add_form()
            assert status is not None and status >= 400, f"duplicate phone {variant} was accepted ({text!r})"
            assert "already exist" in text.lower(), text

    @allure.story("TC-SALE-CU-06: a 9-digit phone is rejected")
    def test_short_phone_is_rejected(self, customers, run_tag):
        customers.open().open_add_form().fill_add_form(f"QA CU Short {run_tag}", unique_phone()[:9])
        status, _, text = customers.submit_add_form()
        assert status is None, f"a 9-digit phone was sent ({text!r})"
        assert "valid phone" in text.lower(), text

    @allure.story("BUG-SALE-051: phone digits beyond the 10th are rejected or kept, never silently dropped")
    @allure.issue("BUG-SALE-051")
    def test_extra_phone_digits_are_not_silently_dropped(self, customers, run_tag):
        typed = unique_phone() + "45"
        customers.open().open_add_form().fill_add_form(f"QA CU Long {run_tag}", typed)
        status, body, text = customers.submit_add_form()
        if status is not None and status < 300:
            assert _digits_sent(body) == typed, f"typed {typed} but the customer was saved with {_digits_sent(body)}"

    @allure.story("BUG-SALE-052: the name is saved trimmed")
    @allure.issue("BUG-SALE-052")
    def test_name_is_saved_trimmed(self, customers, run_tag):
        customers.open().open_add_form().fill_add_form(f"   QA CU Trim {run_tag}   ", unique_phone())
        status, body, text = customers.submit_add_form()
        assert status is not None and status < 300, text
        sent = re.search(r'"customerName"\s*:\s*"([^"]*)"', body).group(1)
        assert sent == sent.strip(), f"name sent with spaces: {sent!r}"

    @allure.story("TC-SALE-CU-08: 255 characters are accepted and 256 are rejected")
    def test_name_length_boundary(self, customers):
        customers.open().open_add_form().fill_add_form("N" * 256, unique_phone())
        status, _, text = customers.submit_add_form()
        assert status is not None and status >= 400, f"a 256-character name was accepted ({text!r})"
        assert "255" in text, text

    @allure.story("BUG-SALE-053: the opening balance keeps two decimals")
    @allure.issue("BUG-SALE-053")
    def test_opening_balance_keeps_two_decimals(self, customers, run_tag):
        name = f"QA CU Dec {run_tag}"
        customers.open().create(name, balance=10.55, balance_type="Advance")
        customers.open().search(name)
        assert customers.balance(name) == pytest.approx(-10.55), "an Advance of Tk 10.55 is not shown as 10.55"


@allure.epic("Sale")
@allure.feature("Customer")
class TestCustomerAccount:

    @allure.story("TC-SALE-CU-18: a payment reduces the Due")
    def test_payment_reduces_due(self, customers, run_tag):
        name = f"QA CU Pay {run_tag}"
        customers.open().create(name, balance=100, balance_type="Due")
        customers.open().search(name)
        customers.open_payment_form(name).fill_payment(30)
        status, _, text = customers.confirm_payment()
        assert status is not None and status < 300, text
        customers.open().search(name)
        assert customers.balance(name) == pytest.approx(70.0)

    @allure.story("BUG-SALE-028: a Bad Debts write-off needs a reason")
    @allure.issue("BUG-SALE-028")
    def test_bad_debt_needs_a_reason(self, customers, run_tag):
        name = f"QA CU Bad {run_tag}"
        customers.open().create(name, balance=100, balance_type="Due")
        customers.open().search(name)
        customers.open_payment_form(name).fill_payment(10, ptype="Bad Debts")
        status, body, text = customers.confirm_payment()
        assert status is None or status >= 400, f"a write-off without a note was accepted: {body[:160]!r}"

    @allure.story("TC-SALE-CU-17: an edited name is saved")
    def test_edit_customer_persists(self, customers, run_tag):
        name = f"QA CU Edit {run_tag}"
        customers.open().create(name)
        customers.open().search(name)
        customers.open_edit(name)
        new_name = f"{name} v2"
        customers._type(customers.name_input, new_name)
        status, body = customers.save_edit()
        assert status < 300, body[:200]
        customers.open().search(new_name)
        assert customers.row(new_name).count() == 1

    @allure.story("TC-SALE-CU-14: search ignores case and matches part of the phone")
    def test_search_ignores_case_and_matches_partial_phone(self, customers, run_tag):
        name = f"QA CU Find {run_tag}"
        phone = customers.open().create(name)
        for text in (name.upper(), phone[-6:]):
            customers.open().search(text)
            assert customers.row(name).count() == 1, f"searching {text!r} did not find the customer"


@allure.epic("Sale")
@allure.feature("Customer at checkout")
class TestCustomerAtCheckout:

    def _to_checkout(self, sale, checkout):
        sale.open()
        sale.add_line(term(PRODUCT), 1, price=50, named=PRODUCT)
        sale.go_to_checkout()

    @allure.story("BUG-SALE-017: a customer's Due is labelled Due at checkout")
    @allure.issue("BUG-SALE-017")
    def test_due_is_labelled_due(self, customers, sale, checkout, run_tag, default_config):
        name = f"QA CU Lbl {run_tag}"
        customers.open().create(name, balance=100, balance_type="Due")
        self._to_checkout(sale, checkout)
        panel = checkout.choose_customer(name)
        assert "Previous Balance (Due)" in panel, f"a Tk 100 Due is not labelled Due: {panel!r}"

    @allure.story("BUG-SALE-029: the customer's default discount is applied at checkout")
    @allure.issue("BUG-SALE-029")
    def test_default_discount_is_applied(self, customers, sale, checkout, run_tag, default_config):
        name = f"QA CU Disc {run_tag}"
        customers.open().create(name, discount=5)
        self._to_checkout(sale, checkout)
        checkout.choose_customer(name)
        assert checkout.discount_input.input_value() == "5", "the 5 % default discount was not filled in"
