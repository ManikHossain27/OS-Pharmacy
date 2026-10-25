"""Inventory Return interplay with Sale (product owner): once pieces are sold the batch stock goes down, and only the
AVAILABLE quantity can be returned - from the Inventory Return tab and from the Inventory Record.

Each test buys its own batch of a product nothing else uses (product, one batch), so a sale of that product can
only draw on that batch and the stock arithmetic is exact."""
from __future__ import annotations

import os

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from pages.sale_page import SalePage
from tests.inventory.return_module.helpers import TOL, batch_stock, checkout_and_complete, supplier_balance
from utils.inventory_scenarios import CART_SHAPES, LineSpec

ROUND = pytest.approx
SEARCH_TERMS = ("A CAL VET", "A GROW", "A SOL", "ACI", "ACCU", "ABA", "ACE", "ACT", "AD", "AE")
CART_SHAPES.setdefault("sale_single", (LineSpec("P3", box_qty=20, btp_vat_per_box=50, retail=80, wholesale=70,
                                                min_qty=0, rack="S1"),))


@pytest.fixture()
def sale_product(page, pharmacy) -> str:
    """A product that has no stock anywhere in this pharmacy and is the first match for its own name, so the batch the
    test buys is the ONLY stock a sale can draw on (a sale takes the oldest stock first)."""
    sale = SalePage(page).open()
    for term in SEARCH_TERMS:
        for text in sale.product_options(term)[:15]:
            name = text.split(" | ")[0].strip()
            if not name or len(name) < 3:
                continue
            first = sale.product_options(name)
            if first and first[0].split(" | ")[0].strip() == name and sale.stock_in_dropdown(name)[0] == 0:
                return name
    pytest.skip("no product without stock found to sell")


@pytest.fixture()
def catalogue(inventory_data, sale_product) -> list[str]:
    """The pool's three products plus the sale product as P3."""
    if os.getenv("QA_PRODUCTS"):
        base = [p.strip() for p in os.getenv("QA_PRODUCTS").split(",")]
    else:
        base = list(inventory_data.get("default_mode_products", ["TEST PRODUCT", "100%", "3 BION"]))
    return base[:3] + [sale_product]


@pytest.fixture()
def stock(page, create, sale_product):
    """A freshly bought single-batch inventory of the sale product: (saved, batch, pieces bought, product)."""
    saved = create("sale_single", paid_ratio=0.0, choice="Due & Buy")
    batch = saved.journey.batches[0]
    pieces = batch_stock(InventoryReturnPage(page).open(), sale_product, batch)
    assert pieces, "the new batch has no stock on the Return form"
    return Bought(saved, batch, pieces, sale_product)


class Bought(tuple):
    """(saved, batch, pieces, product) with names."""
    def __new__(cls, saved, batch, pieces, product):
        return super().__new__(cls, (saved, batch, pieces))

    def __init__(self, saved, batch, pieces, product):
        self.product = product


def _sold(page, product, qty, unit="pc"):
    status, body = SalePage(page).sell(product, qty, unit)
    assert status in (200, 201), f"the sale failed: {status} {body[:200]}"


def _left(page, product, batch):
    """Pieces of the batch the Return form still offers; None when it (or the whole product) is no longer listed."""
    try:
        return batch_stock(InventoryReturnPage(page).open(), product, batch)
    except Exception as exc:                      # a product without any stock is not in the Product dropdown
        if "to be visible" in str(exc):
            return None
        raise


@allure.epic("Inventory")
@allure.feature("Inventory Return - after Sale")
class TestReturnAfterSale:
    @allure.story("A sale lowers the stock the Return form offers for the batch")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("qty,unit", [(5, "pc"), (1, "box")], ids=["5pc", "1box"])
    def test_sale_lowers_returnable_stock(self, page, stock, qty, unit):
        saved, batch, pieces = stock; product = stock.product
        sold = qty * (saved.journey.lines[0].qty_per_box if unit == "box" else 1)
        _sold(page, product, qty, unit)
        assert _left(page, product, batch) == pieces - sold

    @allure.story("Returning more than is left after a sale is refused; exactly what is left is accepted")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    def test_over_available_after_sale(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        _sold(page, product, 5)
        ret = InventoryReturnPage(page).open()
        ret.select_product(product)
        ret.select_batch(batch)
        ret.set_qty(pieces - 4)
        if ret.add_enabled():
            ret.add_current()
        assert ret.cart_lines() == [], "a quantity above the available stock was added to the cart"
        ret.add_line(product, batch, pieces - 5, "pc")
        assert ret.cart_lines()[-1].pieces == pieces - 5

    @allure.story("Returning what is left after a sale (menu): stock empties, balance moves by the Final Price")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_return_the_rest_after_sale(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        _sold(page, product, 5)
        bal = supplier_balance(page, saved.supplier)
        ret = InventoryReturnPage(page).open()
        ret.add_line(product, batch, pieces - 5, "pc")
        done = checkout_and_complete(ret, saved.supplier, (10, "%"))
        assert done.status in (200, 201), done.body[:200]
        assert supplier_balance(page, saved.supplier) == ROUND(bal - done.summary["final_price"], abs=TOL)
        assert not _left(page, product, batch)

    @allure.story("Return Inventory from the record after a partial sale offers only the pieces still in stock")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    def test_record_return_after_partial_sale(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        _sold(page, product, 5)
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        lines = ret.cart_lines()
        assert len(lines) == 1 and lines[0].pieces == pieces - 5, \
            f"the record offers {[l.pieces for l in lines]} pieces; only {pieces - 5} are in stock"

    @allure.story("Completing the record return after a partial sale returns only the available pieces")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_record_return_complete_after_partial_sale(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        _sold(page, product, 5)
        bal = supplier_balance(page, saved.supplier)
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        done = checkout_and_complete(ret, saved.supplier)
        if ret.cart_lines() and done.lines and done.lines[0].pieces > pieces - 5:
            assert done.status is not None and done.status >= 400, "more pieces than are in stock were returned"
        else:
            assert done.status in (200, 201), done.body[:200]
            assert supplier_balance(page, saved.supplier) == ROUND(bal - done.summary["final_price"], abs=TOL)
            assert not _left(page, product, batch)

    @allure.story("Return Inventory from the record after EVERYTHING was sold offers nothing to return")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_record_return_after_everything_sold(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        _sold(page, product, pieces)
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        assert ret.cart_lines() == [] or not ret.checkout_enabled(), \
            f"a sold-out inventory still offers {[l.pieces for l in ret.cart_lines()]} pieces for return"

    @allure.story("A batch that is completely sold is no longer offered on the Return form")
    @allure.severity(allure.severity_level.NORMAL)
    def test_sold_out_batch_not_offered(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        _sold(page, product, pieces)
        assert not _left(page, product, batch)


@allure.epic("Inventory")
@allure.feature("Inventory Return - before Sale")
class TestSaleAfterReturn:
    @allure.story("After a return the Sale screen can sell only what is left in stock")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    def test_sale_above_remaining_refused(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        ret = InventoryReturnPage(page).open()
        ret.add_line(product, batch, 7, "pc")
        assert checkout_and_complete(ret, saved.supplier).status in (200, 201)
        status, body = SalePage(page).sell(product, pieces - 6)          # one more than is left
        assert status is None or status >= 400, f"sold {pieces - 6} pc with only {pieces - 7} in stock ({status})"
        assert _left(page, product, batch) == pieces - 7

    @allure.story("After a return the remaining stock can be sold in full")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_sell_remaining_after_return(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        ret = InventoryReturnPage(page).open()
        ret.add_line(product, batch, 7, "pc")
        assert checkout_and_complete(ret, saved.supplier).status in (200, 201)
        _sold(page, product, pieces - 7)
        assert not _left(page, product, batch)

    @allure.story("The Sale screen's stock for the product follows a return")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_sale_screen_stock_follows_return(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        before = SalePage(page).open().stock_in_dropdown(product)[0]
        ret = InventoryReturnPage(page).open()
        ret.add_line(product, batch, 9, "pc")
        assert checkout_and_complete(ret, saved.supplier).status in (200, 201)
        assert SalePage(page).open().stock_in_dropdown(product)[0] == before - 9

    @allure.story("Cancelling a return after the rest was sold puts the returned pieces back in stock")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cancel_return_after_sale(self, page, stock):
        saved, batch, pieces = stock; product = stock.product
        bal = supplier_balance(page, saved.supplier)
        ret = InventoryReturnPage(page).open()
        ret.add_line(product, batch, 7, "pc")
        assert checkout_and_complete(ret, saved.supplier).status in (200, 201)
        _sold(page, product, pieces - 7)
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(rec.first_row()["id"])
        assert _left(page, product, batch) == 7
        assert supplier_balance(page, saved.supplier) == ROUND(bal, abs=TOL)
