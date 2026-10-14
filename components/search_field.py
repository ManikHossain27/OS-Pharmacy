"""Debounced search input wrapper.

The app debounces the keystroke, fires an XHR, then re-renders the table.
``search()`` does not sleep for the debounce - it waits for that request to
settle (``networkidle``) and for any table spinner to clear.  If the caller
passes a ``loading`` locator (e.g. the table's spin element) it is also waited
on explicitly.
"""
from __future__ import annotations

from playwright.sync_api import Locator, Page


class SearchField:
    def __init__(self, page: Page, locator: Locator, *, loading: Locator | None = None):
        self.page = page
        self.loc = locator
        self.loading = loading or page.locator(
            ".ant-spin-spinning, .ant-table-placeholder .ant-spin"
        )

    # ------------------------------------------------------------------
    def _wait_settled(self) -> None:
        # the debounced request fires shortly after the last keystroke; wait for
        # the network to go quiet rather than guessing the debounce interval
        try:
            self.page.wait_for_load_state("networkidle", timeout=6_000)
        except Exception:
            pass
        try:
            self.loading.first.wait_for(state="hidden", timeout=4_000)
        except Exception:
            pass

    def search(self, term: str) -> None:
        self.loc.fill("")
        self.loc.fill(term)
        self._wait_settled()

    def clear(self) -> None:
        self.loc.fill("")
        self._wait_settled()

    def value(self) -> str:
        return self.loc.input_value()
