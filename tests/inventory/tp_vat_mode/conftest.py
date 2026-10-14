"""Fixtures for the TP/VAT-mode suite.

The browser session / pharmacy / run-tag / catalogue fixtures are the Default-mode suite's (one authenticated
session shared by the whole run - the staging portal is a Vite dev build with 40-60 s page loads), re-exported
here so both suites behave identically.
"""
from __future__ import annotations

import pytest

from pages.inventory_flow import TpVatFlow
from pages.inventory_page import InventoryPage
from tests.inventory.default_mode.conftest import catalogue, context, page, pharmacy, run_tag  # noqa: F401


@pytest.fixture()
def tpvat_inventory(page, pharmacy, catalogue) -> InventoryPage:
    """TP/VAT-mode Inventory page with an EMPTY cart and product references wired."""
    inv = InventoryPage(page)
    InventoryPage.product_catalogue = catalogue
    if inv.current_mode() != "TP/VAT" or "tp-vat" not in page.url or not inv.soft_reset():
        inv.open("TP/VAT")
    if inv.cart_row_count():
        inv.clear_cart()
    return inv


@pytest.fixture()
def flow(tpvat_inventory, run_tag) -> TpVatFlow:
    return TpVatFlow(tpvat_inventory, run_tag)
