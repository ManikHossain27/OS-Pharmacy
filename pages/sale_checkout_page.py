"""Sale Checkout (route /sale-checkout): summary figures, overall discount, paid amount and Complete Sale.

Reuses SalePage for the cart; this page object only adds what the checkout screen offers. The summary block at the bottom of
the screen reads: Total Items, Total Price, Discount Amount, [Card Commission], Round Off, Final Price, Total Paid, Due.
"""
from __future__ import annotations

import re

import allure

from pages.base_page import BasePage

LABELS = ("Total Price", "Discount Amount", "Card Commission", "Round Off", "Final Price", "Total Paid", "Due")


def _money(text: str) -> float:
    m = re.search(r"-?[\d,]+(?:\.\d+)?", (text or "").replace("Tk", "").replace(" ", ""))
    return float(m.group().replace(",", "")) if m else float("nan")


class SaleCheckoutPage(BasePage):
    ROUTE = "/sale-checkout"

    def __init__(self, page):
        super().__init__(page)
        self.discount_input = page.get_by_placeholder("Enter discount")
        self.paid_input = page.get_by_placeholder("Enter paid amount").first
        self.complete_btn = page.get_by_role("button", name="Complete Sale")

    def summary(self) -> dict[str, float]:
        """The summary block as numbers, e.g. {'Total Price': 170.0, 'Discount Amount': 16.0, 'Final Price': 144.0, ...}."""
        lines = [ln.strip() for ln in self.page.locator("main").inner_text().splitlines() if ln.strip()]
        start = max(i for i, ln in enumerate(lines) if ln == "Total Items")
        out: dict[str, float] = {}
        for i in range(start, len(lines) - 1):
            if lines[i] in LABELS and lines[i] not in out:
                out[lines[i]] = _money(lines[i + 1])
        return out

    def set_overall_discount(self, value, unit: str = "%") -> "SaleCheckoutPage":
        """Overall discount; ``unit`` is '%' (default) or 'Tk'."""
        if unit != "%":
            select = self.page.locator("main .ant-select").filter(has_text="%").first
            select.click()
            self.page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option").filter(has_text=unit).first.click()
        self.discount_input.fill(str(value))
        self.page.wait_for_timeout(1_200)
        return self

    def choose_customer(self, name: str) -> str:
        """Choose Customer > search > pick; returns the customer panel text (Previous / New Balance, Loyalty Points)."""
        self.page.get_by_text("Choose Customer", exact=True).first.click()
        box = self.page.locator("main .ant-select-input[role=combobox]").first
        box.wait_for(state="visible", timeout=15_000)
        box.click()
        self.page.keyboard.type(name, delay=40)
        option = self.page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option").filter(has_text=name).first
        option.wait_for(state="visible", timeout=30_000)
        option.click()
        self.page.wait_for_timeout(3_000)
        text = self.page.locator("main").inner_text().replace("\n", " | ")
        return text[text.index(name):text.index(name) + 330]

    def set_paid(self, amount) -> "SaleCheckoutPage":
        self.paid_input.fill(str(amount))
        self.page.wait_for_timeout(800)
        return self

    @allure.step("Settle the payment difference: {choice}")
    def settle(self, choice: str) -> tuple[int | None, str]:
        """Click an option of the Excess Payment / Payment Shortfall dialog ('Profit & Sale', 'Advance & Sale',
        'Less & Sale / Discount', 'Due & Sale'); (status, body) of the sale POST."""
        with self.page.expect_response(lambda r: r.request.method == "POST" and "/sales/create/" in r.url,
                                       timeout=30_000) as info:
            self.page.get_by_text(choice).first.click()
        return info.value.status, info.value.text()

    def toast(self) -> str:
        return " | ".join(self.toast_messages())

    @allure.step("Complete Sale (single click)")
    def complete_once(self) -> tuple[int | None, str]:
        """(status, body) of the sale POST; None when no request was sent (e.g. a settlement dialog opened)."""
        try:
            with self.page.expect_response(lambda r: r.request.method == "POST" and "/sales/create/" in r.url,
                                           timeout=90_000) as info:
                self.complete_btn.click()
            return info.value.status, info.value.text()
        except Exception:
            return None, ""

    @allure.step("Complete Sale (double click)")
    def complete_double_click(self) -> list[int]:
        """Statuses of every POST sales/create seen within 10 s of a rapid double click."""
        seen: list[int] = []

        def _on(resp) -> None:
            if resp.request.method == "POST" and "/sales/create/" in resp.url:
                seen.append(resp.status)

        self.page.on("response", _on)
        try:
            self.complete_btn.dblclick()
            self.page.wait_for_timeout(10_000)
        finally:
            self.page.remove_listener("response", _on)
        return seen
