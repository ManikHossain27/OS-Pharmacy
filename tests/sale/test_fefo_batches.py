"""FEFO batch costing (SRS 3.5 / Inventory): a sale takes stock from the batch that expires first and is costed at that batch's cost.

The fixture buys two batches of a product through the Inventory module - the LATER-expiring batch first, so a purchase-order
(FIFO) pick would be wrong - and drains any stock the product already holds. Cost per piece of a batch = BTP+VAT per box / pieces
per box. Sale Details' Cost column is the line's total cost. Needs a product the pharmacy has no other batches of
(env QA_FEFO_PRODUCT, default "3BIOTIC 100GM"); the tests skip when it cannot be emptied.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

import allure
import pytest

from pages.inventory_flow import InventoryFlow
from pages.inventory_page import InventoryPage
from utils.inventory_scenarios import LineSpec, Scenario
from tests.sale.helpers import term

pytestmark = [pytest.mark.sale, pytest.mark.regression]

FEFO_PRODUCT = os.getenv("QA_FEFO_PRODUCT", "3BIOTIC 100GM")
EARLY = (15, "Dec", 2027)       # batch 1 expires first
LATE = (15, "Dec", 2028)        # batch 2 expires later
BOX_COST_1, BOX_COST_2 = 120.0, 240.0
SELL_PRICE = 1000


@dataclass
class Batches:
    qpb: float                  # pieces per box
    cost1: float                # per piece, the early-expiry batch
    cost2: float                # per piece, the late-expiry batch
    pcs1: float
    pcs2: float


def _money(text: str) -> float:
    m = re.search(r"-?[\d,]+(?:\.\d+)?", (text or "").replace("Tk", ""))
    return float(m.group().replace(",", "")) if m else float("nan")


def _sell(sale, checkout, qty):
    sale.open()
    sale.add_line(term(FEFO_PRODUCT), qty, price=SELL_PRICE, named=FEFO_PRODUCT)
    sale.go_to_checkout()
    status, body = checkout.complete_once()
    assert status is not None and status < 300, f"sale of {qty} failed: {status} {body[:200]}"


def _top_cost(sale_record) -> float:
    """Total cost of the newest sale's first line."""
    items = sale_record.open().open_details(0).details_items()
    return _money(items[0][5])


def _buy(page, run_tag, expiry, box_cost) -> float:
    inv = InventoryPage(page)
    InventoryPage.product_catalogue = [FEFO_PRODUCT]
    if not inv.soft_reset():
        inv.open("Default")
    if inv.cart_row_count():
        inv.clear_cart()
    flow = InventoryFlow(inv, run_tag)
    j = flow.fill_cart(Scenario("fefo", (LineSpec("P0", box_qty=1, btp_vat_per_box=box_cost, retail=SELL_PRICE,
                                                  wholesale=SELL_PRICE, expiry=expiry),)))
    co = flow.open_checkout(j)
    flow.pay(co, j, flow.oracle(j).final_price)
    flow.complete_and_open_details(co, j)
    return j.lines[0].qty_per_box


@pytest.fixture()
def batches(page, pharmacy, sale, checkout, run_tag, default_config) -> Batches:
    """Product emptied, then batch 2 (late expiry, dearer) bought first and batch 1 (early expiry, cheaper) second."""
    pieces = sale.open().stock_in_dropdown(term(FEFO_PRODUCT))[0]
    if pieces < 0:                                    # earlier out-of-stock sales left it negative: buy it back to >= 0
        _buy(page, run_tag, LATE, BOX_COST_2)
        pieces = sale.open().stock_in_dropdown(term(FEFO_PRODUCT))[0]
    if pieces > 0:
        _sell(sale, checkout, int(pieces))
    if sale.open().stock_in_dropdown(term(FEFO_PRODUCT))[0] != 0:
        pytest.skip(f"{FEFO_PRODUCT} could not be emptied")
    qpb = _buy(page, run_tag, LATE, BOX_COST_2)
    _buy(page, run_tag, EARLY, BOX_COST_1)
    return Batches(qpb, BOX_COST_1 / qpb, BOX_COST_2 / qpb, qpb, qpb)


@allure.epic("Sale")
@allure.feature("FEFO batches")
class TestFefo:

    @allure.story("TC-SALE-IV-02: the first piece is costed at the batch that expires first")
    def test_sale_takes_earliest_expiry_batch(self, batches, sale, checkout, sale_record):
        _sell(sale, checkout, 1)
        assert _top_cost(sale_record) == pytest.approx(batches.cost1, abs=0.02)

    @allure.story("TC-SALE-IV-03: a sale larger than batch 1 spills into batch 2 at batch 2's cost")
    def test_sale_spills_into_next_batch(self, batches, sale, checkout, sale_record):
        extra = 1                                   # a box can be a single piece, so batch 2 may hold only 1
        _sell(sale, checkout, int(batches.pcs1) + extra)
        expected = batches.pcs1 * batches.cost1 + extra * batches.cost2
        assert _top_cost(sale_record) == pytest.approx(expected, abs=0.05)

    @allure.story("TC-SALE-IV-07: returning a whole sale puts the pieces back into the batch they came from")
    def test_return_restores_the_source_batch(self, batches, sale, checkout, sale_record, sale_return):
        _sell(sale, checkout, int(batches.pcs1))                     # empties batch 1
        sale_return.open_from_record(sale_record.open(), 0)
        sale_return.set_return_qty(0, int(batches.pcs1)).go_to_return_checkout()
        status, body = sale_return.complete_once()
        assert status is not None and status < 300, f"return failed: {status} {body[:200]}"
        _sell(sale, checkout, 1)
        assert _top_cost(sale_record) == pytest.approx(batches.cost1, abs=0.02), "the returned pieces went to another batch"

    @allure.story("BUG-SALE-041: selling beyond all stock (Out of Stock Sale ON) is still costed, not left at zero")
    @allure.issue("BUG-SALE-041")
    def test_oversell_is_costed(self, batches, sale, checkout, sale_record, sale_config):
        sale_config.apply({"outOfStockSale": True})
        over = 2
        _sell(sale, checkout, int(batches.pcs1 + batches.pcs2) + over)
        cost_cell = sale_record.open().open_details(0).details_items()[0][5]
        assert "pending" not in cost_cell.lower(), f"the pieces sold beyond stock have no cost: {cost_cell!r}"
        in_stock_cost = batches.pcs1 * batches.cost1 + batches.pcs2 * batches.cost2
        assert _money(cost_cell) > in_stock_cost + 0.01, f"no fallback cost for the oversold pieces: {cost_cell!r}"
