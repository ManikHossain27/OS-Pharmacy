"""Fixtures for the Edit Inventory suite (Inventory Record -> row menu -> Edit Inventory).

Browser session / pharmacy / Default-mode flow fixtures are the Default suite's (one authenticated session per run).
Every test starts from an inventory it created itself, so editing never touches data it does not own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest

from pages.inventory_edit_page import InventoryEditPage
from pages.inventory_flow import InventoryFlow, Journey, OpeningStockFlow, TpVatFlow
from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.default_mode.conftest import (  # noqa: F401
    catalogue, context, default_inventory, flow, page, pharmacy, run_tag)
from tests.inventory.opening_stock_mode.conftest import opening_inventory  # noqa: F401
from tests.inventory.tp_vat_mode.conftest import tpvat_inventory  # noqa: F401
from utils.inventory_calc import excel_round
from pages.supplier_list_page import SupplierListPage
from utils import opening_scenarios, tpvat_scenarios
from utils.inventory_scenarios import CART_SHAPES, Scenario

PAYMENT_METHOD = "CASH"
MODE_NAMES = ("Default", "TP/VAT", "Opening Stock")
# mode -> (inventory fixture, flow class, cart shapes) for the two non-default modes
_OTHER_MODES = {"TP/VAT": ("tpvat_inventory", TpVatFlow, tpvat_scenarios.CART_SHAPES),
                "Opening Stock": ("opening_inventory", OpeningStockFlow, opening_scenarios.CART_SHAPES)}


@dataclass
class Saved:
    """An inventory the test created: the journey that built it, the id the Record list shows for it, the Final
    Price it was billed and the amount paid."""
    journey: Journey
    inventory_id: str
    supplier: str
    final: float
    paid: float


def create_inventory(flow: InventoryFlow, shape: str = "two_plain", *, discount=None, paid_ratio: float = 1.0,
                     paid_delta: float | None = None, choice: str | None = None,
                     inventory_type: str = "Purchase", shapes=CART_SHAPES) -> Saved:
    """Create an inventory in ``flow``'s mode through the UI and return what was saved (``shapes``: that mode's cart shapes)."""
    scenario = Scenario(id=f"edit-{shape}", lines=shapes[shape], discount=discount,
                        payment_method=PAYMENT_METHOD, inventory_type=inventory_type)
    flow.inventory.open(flow.mode)      # a fresh Inventory page in this mode, whatever the previous test left on screen
    j = flow.fill_cart(scenario)
    co = flow.open_checkout(j)
    final = flow.oracle(j).final_price
    typed = final + paid_delta if paid_delta is not None else final * paid_ratio
    flow.pay(co, j, typed)
    paid = float(excel_round(typed))
    j.paid = paid
    flow.oracle(j, paid)
    dlg = flow.complete_and_open_details(co, j, choice=choice)
    inventory_id = dlg.wait_loaded().inventory_id().strip()
    dlg.close()
    return Saved(j, inventory_id, j.supplier, final, paid)


@pytest.fixture()
def create(flow) -> Callable[..., Saved]:
    """Factory: ``create("two_plain", discount=(10, "%"), paid_ratio=0.5, choice="Due & Buy")``."""
    return lambda *a, **kw: create_inventory(flow, *a, **kw)


@pytest.fixture()
def create_in(request, flow, run_tag) -> Callable[..., Saved]:
    """Factory: ``create_in("TP/VAT", "two_plain", paid_ratio=0.5, choice="Due & Buy")`` - any mode's inventory."""
    def make(mode: str, shape: str = "two_plain", **kw) -> Saved:
        if mode == "Default":
            return create_inventory(flow, shape, **kw)
        fixture, flow_cls, shapes = _OTHER_MODES[mode]
        return create_inventory(flow_cls(request.getfixturevalue(fixture), run_tag), shape, shapes=shapes, **kw)
    return make


@pytest.fixture(params=["TP/VAT", "Opening Stock"], ids=lambda m: m.replace("/", "").replace(" ", "").lower())
def mode(request) -> str:
    """The non-default inventory modes (TP/VAT, Opening Stock) for tests that run once per mode."""
    return request.param


@pytest.fixture()
def mode_saved(create_in, mode) -> Saved:
    """A fully paid two-line inventory created in ``mode``."""
    return create_in(mode, "two_plain")


@pytest.fixture()
def other_supplier(page, saved) -> str:
    """A supplier other than the one ``saved`` was billed to; one is added to the pharmacy when it has only one."""
    suppliers = SupplierListPage(page).open()
    others = [n for n in suppliers.names() if n.lower() != saved.supplier.lower()]
    if not others:
        suppliers.add_supplier("QA Edit Supplier B", "1711223355")
        others = [n for n in suppliers.names() if n.lower() != saved.supplier.lower()]
    return others[0]


@pytest.fixture()
def saved(create) -> Saved:
    """A fully paid two-line Purchase inventory."""
    return create()


@pytest.fixture()
def record(page, saved) -> InventoryRecordPage:
    rec = InventoryRecordPage(page).open()
    rec.reset_filters_btn.click()
    page.wait_for_timeout(1500)
    return rec.wait_loaded()


@pytest.fixture()
def edit(page, record, saved) -> InventoryEditPage:
    """The Edit Inventory screen of ``saved``."""
    return InventoryEditPage(page).open_for(record, saved.inventory_id)
