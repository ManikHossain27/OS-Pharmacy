"""Wrapper for the app's customised AntD single-select.

Confirmed DOM (Add New Product drawer, live 2026-09-08):

    div.ant-select.ant-select-single.ant-select-show-search
      div.ant-select-content[.ant-select-content-has-value][title="<label>"]
          "<selected label text>"                      <- value shown HERE
          div.ant-select-placeholder                    <- shown when empty
          input#<fieldId>.ant-select-input[role=combobox][aria-expanded]
      div.ant-select-suffix (arrow)
    (portal) div.ant-select-dropdown  ->  div.ant-select-item-option[title]

Important: this build renders the selection in ``.ant-select-content`` /
``.ant-select-content-has-value`` - NOT the stock ``.ant-select-selection-item``.

Interaction that works reliably here:
  * open    -> click ``.ant-select-content`` (BasePage.click = native, JS-pointer fallback)
  * filter  -> focus the ``#<fieldId>`` input and type with the real keyboard
              (the option list is virtualised; type to bring the target into view)
  * pick    -> click the ``.ant-select-item-option`` (JS-pointer fallback handles it)
"""
from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from utils.logger import get_logger

log = get_logger("AntdSelect")


class AntdSelect:
    def __init__(self, page: Page, field_id: str | None = None, *, root: Locator | None = None, clicker=None):
        """Either ``field_id`` (the select's real input id - preferred) or a
        ``root`` locator pointing straight at the ``.ant-select`` wrapper, for
        selects whose input id is React-generated / unstable (e.g. the unit and
        payment-method dropdowns on Inventory Checkout)."""
        self.page = page
        self.field_id = field_id
        if root is not None:
            self.root = root
            self.input = root.locator("input.ant-select-input, input[role='combobox']").first
        else:
            assert field_id, "AntdSelect needs either field_id or root"
            self.input = page.locator(f"#{field_id}")
            self.root = self.input.locator(
                "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' ant-select ')][1]"
            )
        self._click = clicker  # BasePage.click, injected by the page object

    # ------------------------------------------------------------------
    @property
    def _content(self) -> Locator:
        return self.root.locator(".ant-select-content, .ant-select-selector").first

    @property
    def _dropdown(self) -> Locator:
        # AntD keeps a just-closed dropdown's node in the DOM through its fade-out,
        # so while switching between selects several
        # ".ant-select-dropdown:not(.hidden)" can co-exist.  The one this select
        # just opened is the LAST in DOM order.
        return self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        ).last

    def is_open(self) -> bool:
        return self.input.get_attribute("aria-expanded") == "true"

    def selected_text(self) -> str:
        content = self.root.locator(".ant-select-content-has-value")
        if content.count():
            # strip the (hidden) input value that lives inside the same node
            return content.first.get_attribute("title") or content.first.inner_text().strip()
        item = self.root.locator(".ant-select-selection-item")
        return item.first.inner_text().strip() if item.count() else ""

    def has_value(self) -> bool:
        return self.root.locator(".ant-select-content-has-value").count() > 0 or bool(self.selected_text())

    # ------------------------------------------------------------------
    def open(self) -> "AntdSelect":
        if self.is_open():
            return self
        if self._click:
            self._click(self._content, expect_effect=self.is_open, description=f"open select #{self.field_id}")
        else:
            self._content.click()
        expect(self._dropdown).to_be_visible(timeout=5_000)
        return self

    def _wait_filtered(self) -> None:
        """After typing into the search box, wait for the (possibly server-side)
        filter to settle instead of guessing a debounce delay."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=4_000)
        except Exception:
            pass
        # the list re-renders in place; give the option list a moment to attach,
        # but only as a bounded condition wait
        try:
            self._dropdown.locator(".ant-select-item").first.wait_for(
                state="attached", timeout=3_000
            )
        except Exception:
            pass  # a filter with no matches is legitimate

    def options(self, *, filter_text: str | None = None) -> list[str]:
        self.open()
        if filter_text:
            self.input.focus()
            self.input.press_sequentially(filter_text, delay=30)
            self._wait_filtered()
        return [t.strip() for t in self._dropdown.locator(".ant-select-item-option").all_inner_texts()]

    def _matches(self, value: str, *, exact: bool) -> bool:
        sel, val = self.selected_text().casefold(), str(value).casefold()
        return sel == val if exact else val in sel

    def select(self, value: str, *, exact: bool = True) -> "AntdSelect":
        # already showing this value?  nothing to do (avoids a needless
        # open/type/click that flakes when the option list won't render).
        if self._matches(value, exact=exact):
            return self

        self.open()
        # the option list is virtualised - type to bring the target into range
        self.input.focus()
        self.input.press_sequentially(value, delay=30)
        self._wait_filtered()

        # Prefer a CSS + :visible match: a virtualised (rc-virtual-list) dropdown
        # keeps an off-screen "measurement" node (e.g. id="..._list_0", a real
        # aria-label, but display:none) that a role-based locator can match
        # AHEAD of the real, visible option - hanging the wait on a node that
        # will never become visible. Give this its own full wait window (an
        # instant `.count()` check races the list's filter/virtualisation
        # render and can read 0 a moment before the real option mounts) before
        # falling back to role-based, which still covers non-virtualised lists.
        opt = self._dropdown.locator(".ant-select-item-option:visible", has_text=value)
        try:
            opt.first.wait_for(state="visible", timeout=8_000)
        except Exception:
            opt = self._dropdown.get_by_role("option", name=value, exact=exact)
            try:
                opt.first.wait_for(state="visible", timeout=8_000)
            except Exception:
                # last resort: the option may already be selected under a
                # different casing / label - accept if the control now shows it
                if self._matches(value, exact=exact):
                    return self
                raise

        if self._click:
            self._click(
                opt.first,
                expect_effect=lambda: self._matches(value, exact=exact),
                description=f"pick option {value!r} in #{self.field_id}",
            )
        else:
            opt.first.click()

        if not self._matches(value, exact=exact):
            raise AssertionError(
                f"AntdSelect #{self.field_id}: expected {value!r}, "
                f"got {self.selected_text()!r} after selection."
            )
        return self

    def clear(self) -> None:
        clear_btn = self.root.locator(".ant-select-clear")
        if not clear_btn.count():
            return
        if self._click:
            self._click(clear_btn, description=f"clear #{self.field_id}")
        else:
            clear_btn.click()
