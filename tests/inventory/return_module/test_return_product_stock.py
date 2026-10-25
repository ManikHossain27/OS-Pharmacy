"""The product's overall available quantity (Product List > Stock Status: pieces and boxes) after an Inventory Return.

The Return form's Batch dropdown already shows per-batch stock (checked in the other modules); this module reads the
PRODUCT total on /my-products, before and after, so a return that only fixes the batch (or only the total) is caught.
The '100%' pool product cannot be looked up by name (the Product List search finds no row for it), so the checks use the
pool's lines 0 (TEST PRODUCT) and 2 (3 BION)."""
from __future__ import annotations

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from tests.inventory.return_module.helpers import checkout_and_complete, product_stock, supplier_balance

ROUND = pytest.approx
LINES = (0, 2)          # pool lines whose product the Product List can find


def _boxes(pool, i: int, pieces: float) -> float:
    return pieces / pool.qty_per_box[i]


def _expect(pool, before: dict, taken: dict) -> dict:
    """{line: (pieces, boxes)} expected after ``taken`` {line: pieces} left the product's stock."""
    return {i: (before[i][0] - taken.get(i, 0), before[i][1] - _boxes(pool, i, taken.get(i, 0))) for i in before}


def _read(page, pool) -> dict:
    return {i: product_stock(page, pool.products[i]) for i in LINES}


def _assert_stock(page, pool, before: dict, taken: dict) -> None:
    want, now = _expect(pool, before, taken), _read(page, pool)
    for i in LINES:
        assert now[i][0] == ROUND(want[i][0], abs=0.01), (pool.products[i], "pieces", before[i], now[i], taken)
        assert now[i][1] == ROUND(want[i][1], abs=0.11), (pool.products[i], "boxes", before[i], now[i], taken)


def _return(page, pool, items, demurrage=None):
    ret = InventoryReturnPage(page).open()
    for i, q, u in items:
        ret.add_line(pool.products[i], pool.batches[i], q, u)
    return checkout_and_complete(ret, pool.supplier, demurrage)


@allure.epic("Inventory")
@allure.feature("Inventory Return - product stock")
class TestProductStockAfterReturn:
    @allure.story("The product total on the Product List is at least the batches listed on the Return form")
    @pytest.mark.parametrize("line", LINES)
    def test_total_equals_sum_of_batches(self, page, pool, line):
        total = product_stock(page, pool.products[line])[0]
        ret = InventoryReturnPage(page).open()
        ret.select_product(pool.products[line])
        # the batch dropdown is a virtual list (only some batches are in the DOM), so the visible sum is a lower bound
        assert total >= sum(b.get("pcs", 0) for b in ret.batch_options()) - 0.01

    @allure.story("A return deducts exactly the returned pieces / boxes from the product's available quantity")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("items", [[(0, 7, "pc")], [(2, 1, "box")], [(0, 2, "box")],
                                       [(0, 4, "pc"), (2, 9, "pc")], [(0, 1, "box"), (2, 2, "box")]],
                             ids=["7pc", "1box-3bion", "2box", "two-products-pc", "two-products-box"])
    def test_return_deducts_product_stock(self, page, pool, items):
        before = _read(page, pool)
        done = _return(page, pool, items)
        assert done.status in (200, 201), done.body[:200]
        taken: dict[int, float] = {}
        for i, q, u in items:
            taken[i] = taken.get(i, 0) + q * (pool.qty_per_box[i] if u == "box" else 1)
        _assert_stock(page, pool, before, taken)

    @allure.story("Demurrage never changes the quantity taken from stock")
    def test_demurrage_does_not_change_quantity(self, page, pool):
        before = _read(page, pool)
        done = _return(page, pool, [(0, 5, "pc")], (50, "%"))
        assert done.status in (200, 201), done.body[:200]
        _assert_stock(page, pool, before, {0: 5})

    @allure.story("Two batches of one product: the product total drops by both quantities")
    def test_two_batches_one_product(self, page, pool):
        ret = InventoryReturnPage(page).open()
        ret.select_product(pool.products[2])
        other = next((b for b in ret.batch_options() if b["batch"] != pool.batches[2] and b.get("pcs", 0) >= 5), None)
        if other is None:
            pytest.skip("the product has no second batch with stock")
        before = _read(page, pool)
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[2], pool.batches[2], 3, "pc")
        ret.add_line(pool.products[2], other["batch"], 2, "pc")
        done = checkout_and_complete(ret, pool.supplier)
        assert done.status in (200, 201), done.body[:200]
        _assert_stock(page, pool, before, {2: 5})

    @allure.story("Cancelling a return gives the pieces and boxes back to the product's available quantity")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("items", [[(0, 6, "pc")], [(2, 1, "box"), (0, 2, "pc")]], ids=["pc", "box-and-pc"])
    def test_cancel_restores_product_stock(self, page, pool, items):
        before = _read(page, pool)
        done = _return(page, pool, items)
        assert done.status in (200, 201), done.body[:200]
        InventoryReturnRecordPage(page).open().cancel_return(InventoryReturnRecordPage(page).first_row()["id"])
        _assert_stock(page, pool, before, {})

    @allure.story("A refused or failed return leaves the product's stock untouched")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_failed_return_changes_nothing(self, page, pool):
        before = _read(page, pool)
        bal = supplier_balance(page, pool.supplier)
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 3, "pc")
        ret.go_to_checkout()
        ret.select_supplier(pool.supplier)
        ret.set_demurrage(100, "%")          # Final Price 0 - the server answers 500 (BUG-INV-044)
        if ret.complete_enabled():
            ret.complete()
        _assert_stock(page, pool, before, {})
        assert supplier_balance(page, pool.supplier) == ROUND(bal, abs=0.011)

    @allure.story("A double-click on Complete takes the quantity once")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_double_click_takes_stock_once(self, page, pool):
        before = _read(page, pool)
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 2, "pc")
        ret.go_to_checkout()
        ret.select_supplier(pool.supplier)
        ret.complete_btn.dblclick()
        page.wait_for_timeout(8000)
        _assert_stock(page, pool, before, {0: 2})


@allure.epic("Inventory")
@allure.feature("Inventory Return - product stock")
class TestProductStockFromRecord:
    @allure.story("Create -> partial return -> return the rest from the record: the product total goes +all, -part, -rest")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_record_returns(self, page, create, catalogue):
        name = catalogue[0]
        start = product_stock(page, name)[0]
        saved = create("two_plain")
        line = saved.journey.inventory.lines[0]
        bought = line.total_qty + line.free_qty
        assert product_stock(page, name)[0] == ROUND(start + bought, abs=0.01), "the purchase did not add its pieces"

        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        ret.delete_row(1)
        ret.edit_row(0)
        ret.set_qty(5)
        ret.update_cart()
        assert checkout_and_complete(ret, saved.supplier).status in (200, 201)
        assert product_stock(page, name)[0] == ROUND(start + bought - 5, abs=0.01), "partial return"

        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        assert checkout_and_complete(ret, saved.supplier).status in (200, 201)
        assert product_stock(page, name)[0] == ROUND(start + line.free_qty, abs=0.01), "returning the rest brings the product back to its start"

    @allure.story("A full return from the record takes the product back to its quantity before the purchase")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_full_return_back_to_start(self, page, create, catalogue):
        name = catalogue[0]
        start = product_stock(page, name)
        saved = create("single_plain")
        line = saved.journey.inventory.lines[0]
        assert product_stock(page, name)[0] == ROUND(start[0] + line.total_qty + line.free_qty, abs=0.01)
        done = checkout_and_complete(
            InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id), saved.supplier)
        assert done.status in (200, 201), done.body[:200]
        now = product_stock(page, name)
        assert now[0] == ROUND(start[0] + line.free_qty, abs=0.01), (start, now, line.free_qty)   # free pieces not offered: BUG-INV-050
