"""Supplier List (route: /supplier).

Used by the inventory suite to read a supplier's running balance before and after
an inventory is completed (Due / Less / Advance & Buy change it - spec 44.1, workbook M2-M5).

The Balance cell renders a badge ("Due" | "Advance") above the amount, e.g.
``Advance\\nTk 842``; ``balance()`` returns it SIGNED the way the workbook does
(M2: positive = the pharmacy owes the supplier, negative = the supplier holds an advance).
"""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from pages.base_page import BasePage
from utils.constants import ROUTES
from utils.helpers import money


class SupplierListPage(BasePage):
    route = ROUTES["supplier_list"]

    def __init__(self, page: Page):
        super().__init__(page)
        self.rows = page.locator("tbody tr.ant-table-row")

    def open(self) -> "SupplierListPage":
        super().open()
        return self.wait_loaded()

    def wait_loaded(self, timeout: int = 60_000) -> "SupplierListPage":
        expect(self.page.get_by_text("Supplier List", exact=True).first).to_be_visible(timeout=timeout)
        expect(self.rows.first).to_be_visible(timeout=timeout)
        self.page.wait_for_timeout(500)
        return self

    # ------------------------------------------------------------------ reads
    def names(self) -> list[str]:
        return [r.locator("td").first.inner_text().strip() for r in self.rows.all()]

    def _row(self, name: str):
        return self.rows.filter(has_text=re.compile(rf"^\s*{re.escape(name)}\b", re.I)).first

    def balance_text(self, name: str) -> str:
        return self._row(name).locator("td").nth(4).inner_text().strip()

    def balance(self, name: str) -> float:
        """Signed balance: Due -> +amount, Advance -> -amount, anything else -> 0."""
        text = self.balance_text(name)
        amount = money(text)
        if re.search(r"advance", text, re.I):
            return -abs(amount)
        if re.search(r"due", text, re.I):
            return abs(amount)
        return 0.0

    def total_purchases(self, name: str) -> int:
        return int(float(money(self._row(name).locator("td").nth(2).inner_text())))

    def first_supplier(self) -> str:
        return self.names()[0]
