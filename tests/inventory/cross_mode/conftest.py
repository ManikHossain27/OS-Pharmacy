"""Fixtures for the cross-mode suite (spec sections 3, 29, 33-34 and the 'three modes stay independent' rule).

Browser session / pharmacy / run-tag / catalogue fixtures are the Default-mode suite's (one authenticated session
for the whole run).  ``modes`` hands out one flow per Inventory Mode over ONE InventoryPage, every mode starting with
an EMPTY cart and its Add Items drawer OPEN (the drawer and the cart are remembered per mode by the application).
"""
from __future__ import annotations

import pytest

from pages.inventory_flow import InventoryFlow, OpeningStockFlow, TpVatFlow
from pages.inventory_page import InventoryPage
from tests.inventory.default_mode.conftest import catalogue, context, page, pharmacy, run_tag  # noqa: F401
from utils.inventory_scenarios import CART_SHAPES as DEFAULT_SHAPES, Scenario
from utils.opening_scenarios import CART_SHAPES as OPENING_SHAPES
from utils.tpvat_scenarios import CART_SHAPES as TPVAT_SHAPES

MODES = ("Default", "TP/VAT", "Opening Stock")
SHAPES = {"Default": DEFAULT_SHAPES, "TP/VAT": TPVAT_SHAPES, "Opening Stock": OPENING_SHAPES}


class Modes:
    def __init__(self, inv: InventoryPage, run_tag: str):
        self.inv = inv
        self.flows = {"Default": InventoryFlow(inv, run_tag), "TP/VAT": TpVatFlow(inv, run_tag),
                      "Opening Stock": OpeningStockFlow(inv, run_tag)}

    def go(self, mode: str) -> InventoryPage:
        self.inv.switch_mode(mode)
        return self.inv

    def fill(self, mode: str, shape: str = "single_plain"):
        """Switch to ``mode`` and put the shape's lines into ITS cart; returns the Journey."""
        self.go(mode)
        self.inv.open_add_items_panel()
        return self.flows[mode].fill_cart(Scenario(f"x-{mode}-{shape}", SHAPES[mode][shape]))

    def reset(self) -> None:
        """Every mode: empty cart, drawer open."""
        for m in MODES:
            self.go(m)
            self.inv.open_add_items_panel()
            if self.inv.cart_row_count():
                self.inv.clear_cart()


@pytest.fixture()
def modes(page, pharmacy, catalogue, run_tag) -> Modes:
    inv = InventoryPage(page)
    InventoryPage.product_catalogue = catalogue
    if "inventory" not in page.url:
        inv.open("Default")
    m = Modes(inv, run_tag)
    m.reset()
    yield m
    try:
        m.reset()
    except Exception:
        pass
