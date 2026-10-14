"""Generic AntD-style data table.

The app renders the header and body as two separate <table> elements inside a
scroll wrapper, so this component keys off the body rows and maps them onto the
header labels.
"""
from __future__ import annotations

import re

from playwright.sync_api import Locator, Page


class DataTable:
    def __init__(self, page: Page, root: Locator | None = None):
        self.page = page
        self.root = root or page.locator("main")

    # ------------------------------------------------------------------
    @property
    def _header_cells(self) -> Locator:
        return self.root.locator("thead th, [role='columnheader']")

    @property
    def rows(self) -> Locator:
        # AntD renders a hidden zero-height "ant-table-measure-row" (used for
        # column-width measurement, aria-hidden="true") as the first <tbody tr>
        # - exclude it via :not() (the class/attribute is on the <tr> itself,
        # not a descendant, so `filter(has_not=...)` can't see it), or any
        # positional access (.rows.nth(0)) silently grabs that phantom row
        # instead of the first real one.
        return self.root.locator(
            "tbody tr:not(.ant-table-measure-row):not([aria-hidden='true'])"
        ).filter(has_not=self.page.locator(".ant-empty, [class*='empty']"))

    def headers(self) -> list[str]:
        return [h.strip() for h in self._header_cells.all_inner_texts()]

    def row_count(self) -> int:
        # `rows` already excludes the AntD empty-state placeholder row (it
        # matches `has_not=".ant-empty"`), so count it directly - gating
        # through `is_empty()` (which scans the whole `root`, e.g. "main")
        # false-positives whenever an unrelated closed filter Select elsewhere
        # on the page carries its own hidden "No data" empty-dropdown node.
        return self.rows.count()

    def is_empty(self) -> bool:
        # `.ant-table-placeholder` is AntD's own "this table has no rows" row -
        # scoped to an actual table, so it can't false-positive on an unrelated
        # empty Select elsewhere on the page the way a root-wide text/class
        # search can.
        if self.root.locator(".ant-table-placeholder").count() > 0:
            return True
        if self.root.locator("tbody .ant-empty").count() > 0:
            return True
        # this build renders "No <entity> found" in the body when there are no
        # rows - scoped to tbody so it can't match a filter dropdown's own
        # (hidden) "No data" placeholder elsewhere on the page.
        return self.root.locator("tbody").get_by_text(
            re.compile(r"No .*(found|data)", re.I)
        ).count() > 0

    def empty_text(self) -> str:
        loc = self.root.locator(".ant-empty-description, .ant-empty")
        return loc.first.inner_text().strip() if loc.count() else ""

    def is_loading(self) -> bool:
        return self.root.locator(".ant-spin-spinning, .ant-table-placeholder .ant-spin").count() > 0

    # ------------------------------------------------------------------
    def cell(self, row_index: int, column: str) -> str:
        headers = self.headers()
        col_idx = headers.index(column)
        return self.rows.nth(row_index).locator("td").nth(col_idx).inner_text().strip()

    def row_by_text(self, text: str) -> Locator:
        return self.rows.filter(has_text=text).first

    def has_row(self, text: str) -> bool:
        return self.rows.filter(has_text=text).count() > 0

    def cell_in_row(self, row_text: str, column: str) -> str:
        col_idx = self.headers().index(column)
        return self.row_by_text(row_text).locator("td").nth(col_idx).inner_text().strip()

    def column_values(self, column: str) -> list[str]:
        headers = self.headers()
        col_idx = headers.index(column)
        out: list[str] = []
        for i in range(self.row_count()):
            out.append(self.rows.nth(i).locator("td").nth(col_idx).inner_text().strip())
        return out

    def sort_by(self, column: str, clicker) -> None:
        header = self._header_cells.filter(has_text=column).first
        clicker(header, description=f"sort by {column}")
