"""Customer List (route /customer): list, Add New Customer drawer, row actions, and the Payment History drawer's Add New Payment.

Balances are shown in the list as "Due | Tk 95" or "Advance | Tk 5". The drawers animate in and out, so every step waits for
the drawer's own fields rather than a fixed delay. Buttons that post money (Confirm New Customer / Confirm New Payment) are
clicked exactly as the tests ask (single or double) - BasePage.click is not used for them because its JS fallback would
re-click.
"""
from __future__ import annotations

import re
import time

import allure

from pages.base_page import BasePage

ROWS = "main tbody tr.ant-table-row"


def unique_phone() -> str:
    """A 10-digit local number (17xxxxxxxx) that is unique per call; the form adds the +880 prefix."""
    return f"17{int(time.time() * 1000) % 100_000_000:08d}"


def _number(text: str) -> float:
    m = re.search(r"-?[\d,]+(?:\.\d+)?", (text or "").replace("Tk", ""))
    return float(m.group().replace(",", "")) if m else float("nan")


class CustomerPage(BasePage):
    ROUTE = "/customer"

    def __init__(self, page):
        super().__init__(page)
        self.add_btn = page.get_by_role("button", name="Add New Customer")
        self.name_input = page.get_by_placeholder("e.g. Rahim Uddin")
        self.phone_input = page.locator("#phoneNumber")
        self.balance_input = page.get_by_placeholder("Balance (Tk)")
        self.confirm_btn = page.get_by_role("button", name="Confirm New Customer")
        self.search_input = page.get_by_placeholder("Search by name or phone")

    @allure.step("Open Customer List")
    def open(self, route: str | None = None) -> "CustomerPage":
        self.page.goto(self.ROUTE)
        self.add_btn.wait_for(state="visible", timeout=120_000)
        self.page.wait_for_timeout(3_000)
        return self

    # ------------------------------------------------------------------ list
    def search(self, text: str) -> "CustomerPage":
        self.search_input.fill(text)
        self.page.wait_for_timeout(4_000)
        return self

    def row(self, text: str):
        return self.page.locator(ROWS).filter(has_text=text).first

    def balance(self, text: str) -> float:
        """Signed balance of the row containing ``text``: Due positive, Advance negative, none 0."""
        cell = self.row(text).inner_text().replace("\n", " ")
        m = re.search(r"(Due|Advance)\s*Tk\s*([\d,]+(?:\.\d+)?)", cell)
        if not m:
            return 0.0
        value = float(m.group(2).replace(",", ""))
        return value if m.group(1) == "Due" else -value

    # ------------------------------------------------------------------ add customer
    def _type(self, field, text) -> None:
        field.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        if str(text) != "":
            self.page.keyboard.type(str(text), delay=8)

    def open_add_form(self) -> "CustomerPage":
        self.add_btn.click()
        self.phone_input.wait_for(state="visible", timeout=15_000)
        self.page.wait_for_timeout(900)
        return self

    def fill_add_form(self, name: str, phone: str, balance=None, balance_type: str = "Due", discount=None) -> "CustomerPage":
        self._type(self.name_input, name)
        self._type(self.phone_input, phone)
        if discount is not None:
            self._type(self.page.get_by_placeholder("Discount percentage (%)"), discount)
        if balance is not None:
            self._type(self.balance_input, balance)
            select = self.page.locator("#balanceType").locator("xpath=ancestor::div[contains(@class,'ant-select')][1]")
            if balance_type.lower() not in select.inner_text().lower():
                select.click()
                self.page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option") \
                    .filter(has_text=balance_type).first.click()
        return self

    def confirm_add_double_click(self) -> int:
        """Double-click Confirm New Customer; how many POST customers/create requests were sent within 8 s."""
        sent: list[str] = []
        handler = lambda r: sent.append(r.url) if r.method == "POST" and "customers/create" in r.url else None  # noqa: E731
        self.page.on("request", handler)
        try:
            self.confirm_btn.dblclick()
            self.page.wait_for_timeout(8_000)
        finally:
            self.page.remove_listener("request", handler)
        return len(sent)

    last_request_body: str = ""

    def submit_add_form(self) -> tuple[int | None, str, str]:
        """Single click on Confirm New Customer; (status, request body, toast / validation text). status None = no request sent."""
        status, body = None, ""
        try:
            with self.page.expect_response(lambda r: r.request.method == "POST" and "customers/create" in r.url, timeout=8_000) as info:
                self.confirm_btn.click()
            status, body = info.value.status, info.value.request.post_data or ""
        except Exception:
            pass
        self.page.wait_for_timeout(1_500)
        self.last_request_body = body
        return status, body, " | ".join(self.toast_messages() + self.form_errors())

    def close_form(self) -> None:
        self.page.keyboard.press("Escape")
        self.phone_input.wait_for(state="hidden", timeout=8_000)
        self.page.wait_for_timeout(1_200)

    @allure.step("Create customer {name} ({balance_type} {balance})")
    def create(self, name: str, phone: str | None = None, balance=None, balance_type: str = "Due", discount=None) -> str:
        """Create a customer with a single click; returns the 10-digit phone used."""
        phone = phone or unique_phone()
        self.open_add_form().fill_add_form(name, phone, balance, balance_type, discount)
        status, body, text = self.submit_add_form()
        assert status is not None and status < 300, f"creating {name} failed: {status} {text}"
        self.page.wait_for_timeout(1_500)
        return phone

    # ------------------------------------------------------------------ payments
    def open_payment_form(self, text: str) -> "CustomerPage":
        """Row actions > Payment History > Add New Payment for the row containing ``text``."""
        self.row(text).locator(".ant-dropdown-trigger, button").last.click()
        self.page.locator(".ant-dropdown:not(.ant-dropdown-hidden) li").filter(has_text="Payment History").click()
        self.page.get_by_role("button", name="Add New Payment").click(timeout=60_000)
        self.page.locator("[role=dialog] input[placeholder='0']").last.wait_for(state="visible", timeout=15_000)
        self.page.wait_for_timeout(800)
        return self

    def confirm_payment(self) -> tuple[int | None, str, str]:
        """Single click on Confirm New Payment; (status, request body, toast / validation text)."""
        status, body = None, ""
        try:
            with self.page.expect_response(lambda r: r.request.method == "POST" and "customer-payments/create" in r.url, timeout=8_000) as info:
                self.page.get_by_role("button", name="Confirm New Payment").click()
            status, body = info.value.status, info.value.request.post_data or ""
        except Exception:
            pass
        self.page.wait_for_timeout(1_500)
        return status, body, " | ".join(self.toast_messages() + self.form_errors())

    def open_edit(self, text: str) -> "CustomerPage":
        self.row(text).locator(".ant-dropdown-trigger, button").last.click()
        self.page.locator(".ant-dropdown:not(.ant-dropdown-hidden) li").filter(has_text="Edit").first.click()
        self.name_input.wait_for(state="visible", timeout=15_000)
        self.page.wait_for_timeout(1_500)
        return self

    def save_edit(self) -> tuple[int | None, str]:
        with self.page.expect_response(lambda r: r.request.method == "PUT" and "customers/update" in r.url, timeout=30_000) as info:
            self.page.get_by_role("button", name=re.compile("Confirm|Update|Save")).last.click()
        self.page.wait_for_timeout(2_500)
        return info.value.status, info.value.request.post_data or ""

    def fill_payment(self, amount, method: str = "CASH", ptype: str | None = None) -> "CustomerPage":
        """Payment amount and method; ``ptype`` selects 'Payment', 'Return' or 'Bad Debts'."""
        if ptype:
            self.page.locator("[role=dialog]").last.get_by_text(ptype, exact=True).click()
            self.page.wait_for_timeout(500)
        self.page.locator("[role=dialog] input[placeholder='0']").last.fill(str(amount))
        self.page.locator("[role=dialog] .ant-select").last.click()
        self.page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option") \
            .filter(has_text=method).first.click()
        self.page.wait_for_timeout(400)
        return self

    def confirm_payment_double_click(self) -> list[int]:
        """Double-click Confirm New Payment; statuses of every POST customer-payments/create seen within 8 s."""
        seen: list[int] = []

        def _on(resp) -> None:
            if resp.request.method == "POST" and "customer-payments/create" in resp.url:
                seen.append(resp.status)

        self.page.on("response", _on)
        try:
            self.page.get_by_role("button", name="Confirm New Payment").dblclick()
            self.page.wait_for_timeout(8_000)
        finally:
            self.page.remove_listener("response", _on)
        return seen
