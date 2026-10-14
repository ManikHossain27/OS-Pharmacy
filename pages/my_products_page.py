"""My Products / Product List  (route: /my-products)."""
from __future__ import annotations

import re

import allure
from playwright.sync_api import Page, expect

from components.data_table import DataTable
from components.pagination import Pagination
from components.search_field import SearchField
from pages.add_product_page import AddProductPage
from pages.base_page import BasePage
from utils.constants import MY_PRODUCTS_SUMMARY_CARDS, ROUTES


class MyProductsPage(BasePage):
    route = ROUTES["my_products"]

    def __init__(self, page: Page):
        super().__init__(page)
        self.heading = page.get_by_text("Product List", exact=True)
        self.add_product_btn = page.get_by_role("button", name="Add New Product")
        self.download_stock_btn = page.get_by_role("button", name="Download Stock List")
        self.reset_filters_btn = page.get_by_role("button", name="Reset Filters")

        self.name_search = SearchField(page, page.get_by_placeholder("Search by name"))
        self.total_products_badge = page.get_by_text("Total Products").locator("xpath=following-sibling::*[1]")

        self.table = DataTable(page)
        self.pagination = Pagination(page)

    # ------------------------------------------------------------------ loaders
    def is_loaded(self) -> bool:
        return self.heading.is_visible() and self.add_product_btn.is_visible()

    def wait_loaded(self) -> "MyProductsPage":
        expect(self.heading).to_be_visible()
        expect(self.add_product_btn).to_be_visible()
        return self

    # ------------------------------------------------------------------ summary
    def summary_card(self, label: str) -> str:
        assert label in MY_PRODUCTS_SUMMARY_CARDS, f"unknown card {label!r}"
        return self.page.get_by_text(label, exact=True).locator("xpath=following-sibling::*[1]").inner_text().strip()

    def total_products(self) -> int:
        txt = self.total_products_badge.inner_text().strip()
        m = re.search(r"\d+", txt)
        return int(m.group()) if m else 0

    # ------------------------------------------------------------------ actions
    @allure.step("Open Add-New-Product drawer")
    def open_add_product(self) -> AddProductPage:
        drawer = AddProductPage(self.page)
        self.click(
            self.add_product_btn,
            expect_effect=drawer.is_open,
            description="Add New Product",
        )
        return drawer.wait_open()

    def search(self, term: str) -> None:
        self.name_search.search(term)

    def reset_filters(self) -> None:
        self.click(self.reset_filters_btn, description="Reset Filters")

    def filter_by(self, *, generic: str | None = None, company: str | None = None,
                  product_type: str | None = None) -> None:
        from components.antd_select import AntdSelect

        if generic is not None:
            AntdSelect(self.page, self._filter_input_id("Generic"), clicker=self.click).select(generic)
        if company is not None:
            AntdSelect(self.page, self._filter_input_id("Company"), clicker=self.click).select(company)
        if product_type is not None:
            AntdSelect(self.page, self._filter_input_id("Product Type"), clicker=self.click).select(product_type)

    def _filter_input_id(self, label: str) -> str:
        loc = self.page.locator(".ant-form-item, div", has_text=label).locator("input[role='combobox']").first
        return loc.get_attribute("id") or ""

    # ------------------------------------------------------------------ row ops
    def has_product(self, name: str) -> bool:
        return self.table.has_row(name)

    def row(self, name: str):
        return self.table.row_by_text(name)

    def open_product(self, name: str) -> None:
        self.click(self.row(name).get_by_role("link").first, description=f"open product {name}")

    def edit_product(self, name: str) -> AddProductPage:
        """Open Edit from the row's '...' action menu (there is no named 'Edit'
        button - it's an icon-triggered AntD dropdown: Edit / Change History /
        Avg Purchase Price Breakdown)."""
        row = self.row(name)
        by_name = row.get_by_role("button", name=re.compile("edit", re.I))
        if by_name.count():
            self.click(by_name, description=f"edit {name}")
        else:
            trigger = None
            for sel in (".ant-dropdown-trigger.custom-drop-down-btn",
                        ".ant-dropdown-trigger",
                        "td:last-child [class*='drop-down']",
                        "td:last-child div[style*='cursor']"):
                cand = row.locator(sel)
                if cand.count():
                    trigger = cand.last          # last icon in the actions cell = the '...'
                    break
            if trigger is None:
                raise AssertionError(
                    f"no row-action trigger found for {name!r} - update the selector"
                )
            self.click(trigger, description=f"open '...' menu for {name}")
            item = self.page.locator(
                ".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-item",
                has_text=re.compile(r"^\s*Edit\s*$"),
            ).first
            expect(item).to_be_visible(timeout=6_000)
            self.click(item, description=f"Edit menu item for {name}")
        return AddProductPage(self.page).wait_open()

    def price_cells(self, name: str) -> dict[str, str]:
        return {
            "purchase": self.table.cell_in_row(name, "Purchase Price"),
            "sale": self.table.cell_in_row(name, "Sale Price"),
        }

    def row_cells(self, name: str) -> dict[str, str]:
        """Whole product row as {header: text}."""
        headers = self.table.headers()
        cells = self.table.row_by_text(name).locator("td").all_inner_texts()
        return {h: c.strip() for h, c in zip(headers, cells) if h}

    def available_qty(self, name: str) -> float | None:
        """Available stock in pieces, read from the first Stock/Qty-like column
        that holds a number (header wording is not guaranteed). None if no such column."""
        import re as _re
        for h, text in self.row_cells(name).items():
            if _re.search(r"(stock|qty|quantity|available)", h, _re.I) and not _re.search(r"status|min", h, _re.I):
                m = _re.search(r"-?\d[\d,]*\.?\d*", text)
                if m:
                    return float(m.group().replace(",", ""))
        return None

    def stock_status(self, name: str) -> str:
        return self.table.cell_in_row(name, "Stock Status")

    def location(self, name: str) -> str:
        return self.table.cell_in_row(name, "Location")
