"""Cashier queue (route /cashier): sales sent from the counter while Settings > Sale Config > Separate Cashier is ON.

Left: the queue (cards, a search box, Complete all). Right: the open sale with editable Discount, Card Commission, Customer
Paid + tender, Cash Received and Note, and Complete Sale. The queue's own search does not find anything today (BUG-SALE-018).
"""
from __future__ import annotations

import re

import allure

from pages.base_page import BasePage


class CashierPage(BasePage):
    ROUTE = "/cashier"

    def __init__(self, page):
        super().__init__(page)
        self.discount_input = page.get_by_placeholder("Enter discount")
        self.complete_btn = page.get_by_role("button", name="Complete Sale")
        self.complete_all_btn = page.get_by_role("button", name="Complete all")

    @allure.step("Open Cashier")
    def open(self, route: str | None = None) -> "CashierPage":
        self.page.goto(self.ROUTE)
        self.page.get_by_text("Waiting in Queue").first.wait_for(timeout=120_000)
        self.page.wait_for_timeout(6_000)               # the queue list loads after the header
        return self

    def queue_count(self) -> int:
        m = re.search(r"Waiting in Queue\s*(\d+)", self.page.locator("main").inner_text())
        return int(m.group(1)) if m else 0

    def open_sale_id(self) -> str:
        m = re.search(r"(SALE_\d{8}_\d+)", self.page.locator("main").inner_text())
        return m.group(1) if m else ""

    def set_discount(self, pct) -> "CashierPage":
        self.discount_input.fill(str(pct))
        self.page.wait_for_timeout(1_200)
        return self

    @allure.step("Cashier: Complete Sale")
    def complete(self) -> str:
        """Click Complete Sale and return the toast text ('... has been checked out successfully' on success)."""
        self.complete_btn.click()
        for _ in range(30):
            self.page.wait_for_timeout(500)
            msgs = self.toast_messages()
            if msgs:
                return " | ".join(msgs)
        return ""
