"""Fixtures for the Opening Stock-mode suite.

Browser session / pharmacy / run-tag / catalogue fixtures are the Default-mode suite's (one authenticated
session for the whole run - the staging portal is a Vite dev build with 40-60 s page loads).
"""
from __future__ import annotations

import pytest

from pages.inventory_flow import OpeningStockFlow
from pages.inventory_page import InventoryPage
from tests.inventory.default_mode.conftest import catalogue, context, page, pharmacy, run_tag  # noqa: F401


@pytest.fixture()
def opening_inventory(page, pharmacy, catalogue) -> InventoryPage:
    """Opening Stock-mode Inventory page with an EMPTY cart and product references wired."""
    inv = InventoryPage(page)
    InventoryPage.product_catalogue = catalogue
    if "opening-stock" not in page.url or inv.current_mode() != "Opening Stock" or not _clean(inv):
        inv.open("Opening Stock")
    if inv.cart_row_count():
        inv.clear_cart()
    _reset_percentage(inv)
    return inv


def _reset_percentage(inv: InventoryPage) -> None:
    """Clearing the form does not touch Opening Stock (%) and re-selecting the same product keeps it, so a test
    that changed the % would leak it into the next one."""
    try:
        if inv.value_of("opening_stock_percent").strip() != "12":
            inv.set_value("opening_stock_percent", 12)
            inv.field("opening_stock_percent").blur()
            inv.page.wait_for_timeout(200)
    except Exception:
        pass


def _clean(inv: InventoryPage) -> bool:
    try:
        inv.open_add_items_panel()
        if inv._form_clean():
            return True
        inv._clear_form()
        return inv._form_clean()
    except Exception:
        return False


@pytest.fixture()
def flow(opening_inventory, run_tag) -> OpeningStockFlow:
    return OpeningStockFlow(opening_inventory, run_tag)
