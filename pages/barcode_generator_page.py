"""Barcode Generator  (route: /generate-barcode).

Reality captured 2026-09-09 (the earlier model - a multi-select combobox + a
'Generate' button - did NOT match the live build):

  * The page is a TABLE of the pharmacy's own products
    (columns: [chk] Product Details | Company | Barcode | Stock Qty |
     Print Qty | Action | ).
  * Controls above the table:
      - Search "by product name, generic, strength, type..."
      - Company filter (AntD select, 'All companies')
      - "Set all selected item qty" number input + Apply  (Apply enabled only
        when >=1 row is checked AND a qty is entered)
      - "Per row barcode" select  (options 1..6 - labels per printed row)
      - Reset Filters
      - "Fill up all print qty based on stock qty" button
  * Per-row "Print Qty" is an InputNumber (min 1 - the decrement is disabled at 1).
  * The per-row Action icon is a PRINTER that calls the browser's NATIVE print
    dialog (window.print via an iframe).  See BUG-BARCODE-001.  Do NOT click it
    in an unattended run - the native modal blocks the whole tab.
"""
from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator, Page, expect

from components.antd_select import AntdSelect
from components.data_table import DataTable
from components.pagination import Pagination
from pages.base_page import BasePage
from utils.constants import ROUTES


class BarcodeGeneratorPage(BasePage):
    route = ROUTES["barcode_generator"]

    def __init__(self, page: Page):
        super().__init__(page)
        self.table = DataTable(page)
        self.pagination = Pagination(page)
        self.search_input = page.get_by_placeholder(re.compile("search by product", re.I)).first
        self.set_all_qty_input = page.get_by_role("spinbutton", name=re.compile(r"^qty$", re.I)).first
        self.apply_btn = page.get_by_role("button", name=re.compile(r"^Apply$", re.I))
        self.reset_btn = page.get_by_role("button", name=re.compile("reset filters", re.I))
        self.fill_from_stock_btn = page.get_by_role(
            "button", name=re.compile("fill up all print qty", re.I)
        )
        self.select_all_checkbox = page.locator("thead input[type=checkbox]").first

    # ------------------------------------------------------------------ load
    def wait_loaded(self) -> "BarcodeGeneratorPage":
        expect(self.page.get_by_text(re.compile("barcode generator", re.I)).first).to_be_visible()
        expect(self.page.locator("table").first).to_be_visible()
        return self

    # ------------------------------------------------------------------ rows
    def row(self, name: str) -> Locator:
        return self.table.row_by_text(name)

    def row_names(self) -> list[str]:
        return self.table.column_values("Product Details")

    def row_checkbox(self, name: str) -> Locator:
        return self.row(name).locator("input[type=checkbox]").first

    def select_row(self, name: str) -> None:
        self.click(self.row_checkbox(name), description=f"select {name}")

    def is_selected(self, name: str) -> bool:
        return self.row_checkbox(name).is_checked()

    def print_qty_input(self, name: str) -> Locator:
        return self.row(name).locator(".ant-input-number-input").first

    def print_qty(self, name: str) -> str:
        return self.print_qty_input(name).input_value()

    def set_print_qty(self, name: str, value) -> None:
        f = self.print_qty_input(name)
        f.fill("")
        f.fill(str(value))

    def barcode_value(self, name: str) -> str:
        return self.table.cell_in_row(name, "Barcode")

    def stock_qty(self, name: str) -> str:
        return self.table.cell_in_row(name, "Stock Qty")

    # ------------------------------------------------------------------ search / filter
    def search(self, term: str) -> None:
        self.search_input.fill("")
        self.search_input.fill(term)
        self._settle()

    def filter_company(self, name: str) -> None:
        AntdSelect(self.page, self._select_id_by_label("Company"), clicker=self.click).select(
            name, exact=False
        )

    def _select_id_by_label(self, label: str) -> str:
        """This build wraps each control as  <div>LABEL</div><div>…ant-select…</div>
        (no <label>, no .ant-form-item).  Anchor on the label text and take the
        combobox input in the sibling that follows it."""
        sel = self.page.locator(
            "xpath=//*[normalize-space(text())=%r]/following-sibling::*[1]"
            "//input[@role='combobox']" % label
        ).first
        sel.wait_for(state="attached", timeout=10_000)
        return sel.get_attribute("id") or ""

    def reset_filters(self) -> None:
        self.click(self.reset_btn, description="Reset Filters")

    # ------------------------------------------------------------------ bulk qty
    def set_all_selected_qty(self, value) -> None:
        self.set_all_qty_input.fill("")
        self.set_all_qty_input.fill(str(value))

    def apply_enabled(self) -> bool:
        return self.apply_btn.is_enabled()

    @allure.step("Apply 'set all selected item qty' = {value}")
    def apply_qty_to_selected(self, value) -> None:
        self.set_all_selected_qty(value)
        self.click(self.apply_btn, description="Apply qty to selected")

    def fill_print_qty_from_stock(self) -> None:
        self.click(self.fill_from_stock_btn, description="Fill up all print qty based on stock qty")

    # ------------------------------------------------------------------ per-row barcode count
    def _per_row_select_id(self) -> str:
        return self._select_id_by_label("Per row barcode")

    def per_row_barcode_options(self) -> list[str]:
        opts = AntdSelect(self.page, self._per_row_select_id(), clicker=self.click).options()
        self.page.keyboard.press("Escape")
        return opts

    def set_per_row_barcode(self, count: int) -> None:
        AntdSelect(self.page, self._per_row_select_id(), clicker=self.click).select(str(count))

    # ------------------------------------------------------------------ print (BUG-BARCODE-001)
    def row_print_icon(self, name: str) -> Locator:
        """The per-row printer icon.  WARNING: clicking it opens Chrome's native
        print dialog (BUG-BARCODE-001) and will block an unattended run - assert
        on its presence, do not click it in CI."""
        return self.row(name).locator("td:last-child div[style*='cursor']").first

    def has_in_app_preview(self) -> bool:
        """BUG-BARCODE-001: there is no in-app label preview - printing goes
        straight to the browser dialog."""
        return self.page.locator(
            "[class*='preview'] svg, [class*='label'] svg, svg.barcode, canvas.barcode"
        ).count() > 0

    def field_errors(self) -> list[str]:
        return self.form_errors()
