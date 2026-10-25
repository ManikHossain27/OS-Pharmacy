"""Fixtures for the Inventory Return suite.

Creating an inventory takes ~5 minutes on staging, so the menu-return tests share one large "pool" inventory (three
products, hundreds of pieces each, bought on credit) and assert DELTAS: batch stock, supplier balance and the Return
Record are read before and after every return. Tests that need an inventory of their own state (return from a record,
partial returns of one record, other modes) create it with ``create_in``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from pages.supplier_list_page import SupplierListPage
from tests.inventory.default_mode.conftest import (  # noqa: F401
    catalogue, context, default_inventory, flow, page, pharmacy, run_tag)
from tests.inventory.edit_module.conftest import (  # noqa: F401
    Saved, create, create_in, create_inventory, mode, mode_saved, record, saved)
from tests.inventory.opening_stock_mode.conftest import opening_inventory  # noqa: F401
from tests.inventory.tp_vat_mode.conftest import tpvat_inventory  # noqa: F401
from utils.inventory_scenarios import CART_SHAPES, LineSpec

# Large, unequal quantities so many returns can draw on the same batches without running a batch dry.
POOL_LINES = (LineSpec("P0", box_qty=2000, btp_vat_per_box=33.3, retail=60, wholesale=50, min_qty=5, rack="A1"),
              LineSpec("P1", box_qty=1000, btp_vat_per_box=125.75, retail=200, wholesale=180, min_qty=2, rack="B2"),
              LineSpec("P2", box_qty=100, btp_vat_per_box=80, retail=120, wholesale=100, min_qty=0, rack="C3"))
CART_SHAPES.setdefault("return_pool", POOL_LINES)
_POOLS: dict[str, "Pool"] = {}


@dataclass
class Pool:
    saved: Saved
    products: list[str]          # search term per line (P0, P1, P2)
    batches: list[str]
    qty_per_box: list[float]
    cost_per_pc: list[float]     # purchase price per piece (the line's final cost / total pieces)

    @property
    def supplier(self) -> str:
        return self.saved.supplier

    def price(self, i: int, pieces: float) -> float:
        """Return price of ``pieces`` pieces of line ``i`` at its purchase price."""
        return round(pieces * self.cost_per_pc[i], 2)


_SLUG = "".join(ch for ch in os.getenv("PHARMACY_NAME", "") if ch.isalnum())
POOL_FILE = Path(__file__).resolve().parents[3] / "logs" / (f"return_pool_{_SLUG}.json" if _SLUG else "return_pool.json")


def _load_pool() -> "Pool | None":
    """The pool a previous run created (it holds hundreds of pieces per batch, so later runs keep drawing on it)."""
    try:
        d = json.loads(POOL_FILE.read_text(encoding="utf-8"))
        return Pool(Saved(None, d["inventory_id"], d["supplier"], d["final"], d["paid"]), d["products"], d["batches"],
                    d["qty_per_box"], d["cost_per_pc"])
    except (OSError, ValueError, KeyError):
        return None


MIN_STOCK = (3000, 300, 300)   # pieces each pool batch must still hold (the 1,000 pc return needs line 0)


def _stocked(page, pl: "Pool") -> bool:
    """True while every pool batch still holds enough pieces for a full run."""
    ret = InventoryReturnPage(page).open()
    for i, need in enumerate(MIN_STOCK):
        ret.select_product(pl.products[i])
        have = next((b["pcs"] for b in ret.batch_options() if b["batch"] == pl.batches[i]), 0)
        if have < need:
            return False
        ret.open()
    return True


@pytest.fixture()
def pool(page, create, catalogue) -> Pool:
    """The shared pool inventory (created on first use, then reused across runs; replaced once a batch runs low)."""
    if "pool" not in _POOLS:
        pl = _load_pool()
        if pl is not None and not _stocked(page, pl):
            pl = None
        if pl is None:
            s = create("return_pool", paid_ratio=0.0, choice="Due & Buy")
            lines = s.journey.inventory.lines
            pl = Pool(s, [catalogue[i] for i in range(len(lines))], list(s.journey.batches),
                      [l.qty_per_box for l in lines], [l.final_line_cost / l.total_qty for l in lines])
            POOL_FILE.parent.mkdir(exist_ok=True)
            POOL_FILE.write_text(json.dumps({"inventory_id": s.inventory_id, "supplier": s.supplier, "final": s.final,
                                             "paid": s.paid, "products": pl.products, "batches": pl.batches,
                                             "qty_per_box": pl.qty_per_box, "cost_per_pc": pl.cost_per_pc}, indent=1),
                                 encoding="utf-8")
        _POOLS["pool"] = pl
    return _POOLS["pool"]


@pytest.fixture()
def ret(page) -> InventoryReturnPage:
    """A freshly loaded Inventory Return form (empty cart)."""
    return InventoryReturnPage(page).open()


@pytest.fixture()
def returns(page) -> InventoryReturnRecordPage:
    return InventoryReturnRecordPage(page)


@pytest.fixture()
def second_supplier(page, pool) -> str:
    """A supplier other than the pool's; one is added to the pharmacy when it has only one."""
    suppliers = SupplierListPage(page).open()
    others = [n for n in suppliers.names() if n.lower() != pool.supplier.lower()]
    if not others:
        suppliers.add_supplier("QA Edit Supplier B", "1711223355")
        others = [n for n in suppliers.names() if n.lower() != pool.supplier.lower()]
    return next((n for n in others if "supplier b" in n.lower()), others[0])
