"""Pagination footer: 'Showing X-Y of Z', prev/next, page numbers, page-size."""
from __future__ import annotations

import re

from playwright.sync_api import Locator, Page


class Pagination:
    def __init__(self, page: Page, root: Locator | None = None):
        self.page = page
        self.root = root or page.locator("main")

    def summary(self) -> str:
        loc = self.root.get_by_text(re.compile(r"Showing"))
        return loc.first.inner_text().strip() if loc.count() else ""

    def total(self) -> int:
        m = re.search(r"of\s+([\d,]+)", self.summary())
        return int(m.group(1).replace(",", "")) if m else 0

    def range(self) -> tuple[int, int]:
        m = re.search(r"(\d+)\s*-\s*(\d+)", self.summary())
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    @property
    def next_btn(self) -> Locator:
        return self.root.get_by_role("listitem", name=re.compile("Next Page", re.I))

    @property
    def prev_btn(self) -> Locator:
        return self.root.get_by_role("listitem", name=re.compile("Previous Page", re.I))

    def go_to_page(self, n: int, clicker) -> None:
        box = self.root.get_by_role("textbox", name=re.compile("Page no", re.I))
        box.fill(str(n))
        box.press("Enter")

    def next(self, clicker) -> None:
        clicker(self.next_btn, description="pagination next")

    def prev(self, clicker) -> None:
        clicker(self.prev_btn, description="pagination prev")

    def set_page_size(self, size: int, clicker) -> None:
        combo = self.root.locator(".ant-select").filter(has_text="Items Per Page").first
        if not combo.count():
            combo = self.root.get_by_role("combobox").last
        clicker(combo, description="open page-size select")
        self.page.get_by_role("option", name=str(size)).first.click()
