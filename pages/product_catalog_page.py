"""Product Catalog  (route: /product-catalog).

Master catalogue of ~41k global products that can be pulled into My Products.
Confirmed live 2026-09-08:

* columns: ``[checkbox] | Name | Company | Purchase/Price | Sale/Price | Status | [Import]``
* per-row action = an **Import** button; once imported it becomes a
  non-interactive **"Imported"** badge (``span.count-badge``)
* ticking row checkboxes shows a bulk bar: **Cancel** + **Import selected (N)**
* the header checkbox selects the ENTIRE result set (all pages)
* filters: Generic / Company / Product Type (AntD selects) + **Reset Filters**
* pagination is URL-synced (``?size=&page=``); a "Go to" page input; items-per-page
  select (10/20/50/100)
* selection count persists across pages / search / filter; checkboxes re-hydrate
* no sortable columns; clicking a row opens nothing
"""
from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator, Page, expect

from components.antd_select import AntdSelect
from components.pagination import Pagination
from components.search_field import SearchField
from components.toast import Toast
from pages.base_page import BasePage
from utils.constants import ROUTES


class ProductCatalogPage(BasePage):
    route = ROUTES["product_catalog"]

    def __init__(self, page: Page):
        super().__init__(page)
        self.toast = Toast(page)
        self.pagination = Pagination(page)
        self.search_field = SearchField(page, page.get_by_placeholder("Search by name"))
        self.reset_filters_btn = page.get_by_role("button", name="Reset Filters")
        self.select_all_checkbox = page.locator("thead input[type=checkbox]").first
        self.bulk_import_btn = page.get_by_role("button", name=re.compile(r"Import selected", re.I))
        self.bulk_cancel_btn = page.locator(".ant-drawer-open, main").get_by_role("button", name="Cancel")

    # ------------------------------------------------------------------ rows
    @property
    def _body(self) -> Locator:
        # the data rows live in the 2nd <table>; skip the hidden header-mirror row
        return self.page.locator("main table").nth(1).locator("tbody tr").filter(
            has=self.page.locator("input[type=checkbox]")
        )

    def wait_loaded(self) -> "ProductCatalogPage":
        expect(self.page.locator("main table").nth(1)).to_be_visible()
        return self

    def row_count(self) -> int:
        return self._body.count()

    def row(self, name: str) -> Locator:
        return self._body.filter(has_text=name).first

    def row_names(self) -> list[str]:
        return [r.locator("td").nth(1).inner_text().strip() for r in self._body.all()]

    def row_checkbox(self, name: str) -> Locator:
        return self.row(name).locator("input[type=checkbox]")

    def is_selected(self, name: str) -> bool:
        return self.row(name).locator(".ant-checkbox-checked").count() > 0

    def status_of(self, name: str) -> str:
        return self.row(name).locator("td").nth(5).inner_text().strip()

    def is_already_imported(self, name: str) -> bool:
        return self.status_of(name).lower() == "imported"

    def is_empty(self) -> bool:
        return self.page.locator("main table .ant-empty").count() > 0 or self.pagination.total() == 0

    # ------------------------------------------------------------------ search / filter
    def search(self, term: str) -> None:
        self.search_field.search(term)

    def filter_by(self, *, generic: str | None = None, company: str | None = None,
                  product_type: str | None = None) -> None:
        if generic is not None:
            self._filter("Generic").select(generic)
        if company is not None:
            self._filter("Company").select(company)
        if product_type is not None:
            self._filter("Product Type").select(product_type)

    def _filter(self, label: str) -> AntdSelect:
        fid = (
            self.page.locator(".ant-select", has_text=label)
            .locator("input")
            .first.get_attribute("id")
        )
        return AntdSelect(self.page, fid, clicker=self.click)

    def reset_filters(self) -> None:
        self.click(self.reset_filters_btn, description="Reset Filters")
        self._settle()

    # ------------------------------------------------------------------ selection
    @allure.step("Select catalog product: {name}")
    def select(self, name: str) -> None:
        self.click(self.row_checkbox(name),
                   expect_effect=lambda: self.is_selected(name),
                   description=f"select {name}")

    def deselect(self, name: str) -> None:
        self.click(self.row_checkbox(name),
                   expect_effect=lambda: not self.is_selected(name),
                   description=f"deselect {name}")

    def select_all(self) -> None:
        self.click(self.select_all_checkbox, description="select all (entire result set)")

    def selected_count(self) -> int:
        """The N in 'Import selected (N)' - the true selection size across pages."""
        if not self.bulk_import_btn.count():
            return 0
        m = re.search(r"\(([\d,]+)\)", self.bulk_import_btn.inner_text())
        return int(m.group(1).replace(",", "")) if m else 0

    def cancel_selection(self) -> None:
        if self.bulk_cancel_btn.count():
            self.click(self.bulk_cancel_btn.first, description="Cancel selection")

    # ------------------------------------------------------------------ import
    @allure.step("Import row: {name}")
    def import_row(self, name: str) -> str:
        self.click(self.row(name).get_by_role("button", name="Import"),
                   description=f"Import {name}")
        return self.toast.wait(timeout=8_000)

    @allure.step("Import selected")
    def import_selected(self) -> str:
        self.click(self.bulk_import_btn, description="Import selected")
        return self.toast.wait(timeout=10_000)

    def add_single(self, name: str) -> str:
        return self.import_row(name)
