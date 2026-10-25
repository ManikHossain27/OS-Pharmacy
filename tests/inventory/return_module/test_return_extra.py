"""Inventory Return - the cases the first four modules leave out: supplier balance signs (Advance / zero), several batches
of one product, menu returns on TP/VAT and Opening Stock inventories, cancelling after the stock moved, repeat returns of
a fully returned inventory, the blank-page probe, and the Return Record's date range, pagination and combined filters."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from pages.supplier_list_page import SupplierListPage
from tests.inventory.return_module.helpers import TOL, batch_stock, checkout_and_complete, supplier_balance

ROUND = pytest.approx


@pytest.fixture()
def zero_supplier(page) -> str:
    """A supplier with no balance (created once per run)."""
    name = f"QA Ret Zero {time.strftime('%m%d%H%M')}"
    suppliers = SupplierListPage(page).open()
    if name not in suppliers.names():
        suppliers.add_supplier(name, "17" + str(int(time.time()))[-8:])
    return name


# ---- supplier balance signs ------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - supplier balance")
class TestBalanceSigns:
    @allure.story("The checkout previews an Advance for a supplier with no balance: New Balance = - Final Price")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("demurrage", [None, (10, "%"), (3, "Tk")], ids=["none", "10pct", "tk3"])
    def test_preview_zero_balance_supplier(self, page, pool, zero_supplier, demurrage):
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 20, "pc")
        ret.go_to_checkout()
        ret.select_supplier(zero_supplier)
        if demurrage:
            ret.set_demurrage(*demurrage)
        s = ret.summary()
        assert s["previous_balance"] == 0 and s["new_balance"] == ROUND(-s["final_price"], abs=TOL), s

    @allure.story("Returning to a supplier with no balance makes that supplier's balance an Advance of the Final Price")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_complete_to_zero_balance_supplier(self, page, pool, zero_supplier):
        before = {n: supplier_balance(page, n) for n in (zero_supplier, pool.supplier)}
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 20, "pc")
        done = checkout_and_complete(ret, zero_supplier, (5, "%"))
        assert done.status in (200, 201), (done.status, done.body[:200])
        after = {n: supplier_balance(page, n) for n in (zero_supplier, pool.supplier)}
        assert after[zero_supplier] == ROUND(before[zero_supplier] - done.summary["final_price"], abs=TOL), (before, after)
        assert after[pool.supplier] == ROUND(before[pool.supplier], abs=TOL), (before, after)

    @allure.story("A supplier already in Advance gets a larger Advance; the Previous Balance preview is negative")
    def test_preview_advance_supplier(self, page, pool, zero_supplier):
        # the zero-balance supplier is in Advance once the previous test's return reached it; otherwise skip
        bal = supplier_balance(page, zero_supplier)
        if bal >= 0:
            pytest.skip("the supplier is not in Advance (see BUG-INV-043)")
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 10, "pc")
        ret.go_to_checkout()
        ret.select_supplier(zero_supplier)
        s = ret.summary()
        assert s["previous_balance"] == ROUND(bal, abs=TOL) and s["new_balance"] == ROUND(bal - s["final_price"], abs=TOL), s


# ---- several batches of one product ---------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - cart")
class TestSeveralBatches:
    @allure.story("Two batches of the same product in one return: each batch loses its own quantity at its own price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_two_batches_one_product(self, page, pool):
        ret = InventoryReturnPage(page).open()
        ret.select_product(pool.products[2])
        other = next((b for b in ret.batch_options() if b["batch"] != pool.batches[2] and b.get("pcs", 0) >= 5), None)
        if other is None:
            pytest.skip("the product has no second batch with stock")
        s0 = batch_stock(ret.open(), pool.products[2], pool.batches[2])
        s1 = batch_stock(ret.open(), pool.products[2], other["batch"])
        bal = supplier_balance(page, pool.supplier)
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[2], pool.batches[2], 3, "pc")
        ret.add_line(pool.products[2], other["batch"], 2, "pc")
        lines = ret.cart_lines()
        assert [l.batch for l in lines] == [pool.batches[2], other["batch"]], lines
        assert ret.cart_total() == ROUND(sum(l.price for l in lines), abs=0.03)
        done = checkout_and_complete(ret, pool.supplier)
        assert done.status in (200, 201), done.body[:200]
        check = InventoryReturnPage(page).open()
        assert batch_stock(check, pool.products[2], pool.batches[2]) == s0 - 3
        assert batch_stock(check.open(), pool.products[2], other["batch"]) == s1 - 2
        assert supplier_balance(page, pool.supplier) == ROUND(bal - done.summary["final_price"], abs=TOL)
        assert InventoryReturnRecordPage(page).open().first_row()["items"].startswith("2")


# ---- menu returns on the other inventory modes ----------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - modes")
class TestMenuReturnOtherModes:
    @allure.story("A TP/VAT / Opening Stock inventory is returned from the Inventory Return menu at its purchase price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_menu_return(self, page, mode_saved, catalogue):
        saved = mode_saved
        o = saved.journey.inventory.lines[0]
        batch = saved.journey.batches[0]
        ret = InventoryReturnPage(page).open()
        stock = batch_stock(ret, catalogue[0], batch)
        assert stock == o.total_qty + o.free_qty or stock == o.total_qty, stock
        bal = supplier_balance(page, saved.supplier)
        ret = InventoryReturnPage(page).open()
        ret.add_line(catalogue[0], batch, 2, "pc")
        line = ret.cart_lines()[0]
        assert line.price == ROUND(2 * o.final_line_cost / o.total_qty, abs=0.05), (line, o.final_line_cost, o.total_qty)
        done = checkout_and_complete(ret, saved.supplier, (10, "%"))
        assert done.status in (200, 201), done.body[:200]
        assert batch_stock(InventoryReturnPage(page).open(), catalogue[0], batch) == stock - 2
        assert supplier_balance(page, saved.supplier) == ROUND(bal - done.summary["final_price"], abs=TOL)
        assert InventoryReturnRecordPage(page).open().first_row()["status"] == "Returned"


# ---- cancelling after the stock moved --------------------------------------------------------------------------------
def _return(page, pool, pieces, supplier=None):
    ret = InventoryReturnPage(page).open()
    ret.add_line(pool.products[0], pool.batches[0], pieces, "pc")
    done = checkout_and_complete(ret, supplier or pool.supplier)
    return done, InventoryReturnRecordPage(page).open().first_row()


@allure.epic("Inventory")
@allure.feature("Inventory Return - cancel")
class TestCancelAfterChanges:
    @allure.story("After a return is cancelled the same stock can be returned again")
    def test_return_again_after_cancel(self, page, pool):
        s0 = batch_stock(InventoryReturnPage(page).open(), pool.products[0], pool.batches[0])
        done, row = _return(page, pool, 5)
        InventoryReturnRecordPage(page).open().cancel_return(row["id"])
        assert batch_stock(InventoryReturnPage(page).open(), pool.products[0], pool.batches[0]) == s0
        done2, row2 = _return(page, pool, 5)
        assert done2.status in (200, 201) and row2["id"] != row["id"] and row2["status"] == "Returned", (done2.status, row2)
        assert batch_stock(InventoryReturnPage(page).open(), pool.products[0], pool.batches[0]) == s0 - 5

    @allure.story("Cancelling an earlier return after a later one from the same batch restores only the earlier quantity")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cancel_earlier_of_two(self, page, pool):
        s0 = batch_stock(InventoryReturnPage(page).open(), pool.products[0], pool.batches[0])
        bal0 = supplier_balance(page, pool.supplier)
        d1, r1 = _return(page, pool, 6)
        d2, r2 = _return(page, pool, 4)
        InventoryReturnRecordPage(page).open().cancel_return(r1["id"])
        assert batch_stock(InventoryReturnPage(page).open(), pool.products[0], pool.batches[0]) == s0 - 4
        assert supplier_balance(page, pool.supplier) == ROUND(bal0 - d2.summary["final_price"], abs=TOL)

    @allure.story("Cancelling a return whose inventory was cancelled afterwards does not break the page or go negative")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_cancel_return_after_inventory_cancelled(self, page, create):
        saved = create("single_plain")
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        ret.edit_row(0)
        ret.set_qty(5)
        ret.update_cart()
        done = checkout_and_complete(ret, saved.supplier)
        assert done.status in (200, 201), done.body[:200]
        rec = InventoryReturnRecordPage(page).open()
        row = rec.first_row()
        InventoryRecordPage(page).open().cancel_inventory(saved.inventory_id)
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(row["id"])
        rec.open()
        assert rec.row_values(rec.row_by_id(row["id"]))["status"] in ("Returned", "Cancelled")
        assert "error" not in rec.page.locator("body").inner_text().lower()


# ---- a fully returned inventory returned again ---------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - from a record")
class TestRepeatReturn:
    @allure.story("Completing a second full return of an already fully returned inventory is refused by the server")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    def test_second_full_return_refused(self, page, create):
        saved = create("single_plain")
        first = checkout_and_complete(
            InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id), saved.supplier)
        assert first.status in (200, 201), first.body[:200]
        bal = supplier_balance(page, saved.supplier)
        again = checkout_and_complete(
            InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id), saved.supplier)
        assert again.status is None or again.status >= 400, "BUG-INV-047: a second full return was accepted"
        assert supplier_balance(page, saved.supplier) == ROUND(bal, abs=TOL)


# ---- blank-page probe ------------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - form")
class TestFormStability:
    @pytest.mark.negative
    @pytest.mark.parametrize("line", [0, 1, 2])
    def test_fraction_does_not_crash_the_page(self, page, pool, line):
        """2.5 pc typed for any product leaves the form usable (a white page was seen once)."""
        ret = InventoryReturnPage(page).open()
        ret.select_product(pool.products[line])
        ret.select_batch(pool.batches[line])
        ret.set_qty("2.5")
        ret.add_current()
        assert ret.page.locator("#productId").is_visible(), "the Inventory Return page went blank"

    @pytest.mark.negative
    def test_fraction_with_three_lines_in_cart(self, page, pool):
        ret = InventoryReturnPage(page).open()
        for i in (0, 2):
            ret.add_line(pool.products[i], pool.batches[i], 4, "pc")
        ret.select_product(pool.products[1])
        ret.select_batch(pool.batches[1])
        ret.set_qty("2.5")
        ret.add_current()
        assert ret.page.locator("#productId").is_visible(), "the Inventory Return page went blank"
        assert len(ret.cart_lines()) >= 2


# ---- Return Record: date range, pagination, combined filters -------------------------------------------------------
@pytest.fixture()
def rec(page, pool) -> InventoryReturnRecordPage:
    r = InventoryReturnRecordPage(page).open()
    if r.row_count() == 0:
        pytest.skip("no returns yet")
    return r


def _row_day(row) -> datetime:
    return datetime.strptime(row["date"].split(",")[0].strip(), "%d %b %Y")


@allure.epic("Inventory")
@allure.feature("Inventory Return Record")
class TestReturnRecordRangeAndPaging:
    @allure.story("The date range keeps the returns made on those days and drops the others")
    def test_date_range(self, rec):
        first = rec.first_row()
        day = _row_day(first)
        rec.set_date_range(day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"))
        ids = [r["id"] for r in rec.all_rows()]
        assert first["id"] in ids and all(_row_day(r) == day for r in rec.all_rows()), ids

    @allure.story("A range with no returns shows an empty list; Reset Filters restores the list")
    @pytest.mark.negative
    def test_empty_range_and_reset(self, rec):
        full = rec.showing()[2]
        rec.set_date_range("2020-01-01", "2020-01-02")
        assert rec.row_count() == 0
        rec.reset_filters()
        assert rec.showing()[2] == full

    @allure.story("A range that starts after the newest return excludes it")
    @pytest.mark.negative
    def test_range_after_newest(self, rec):
        first = rec.first_row()
        later = _row_day(first) + timedelta(days=2)
        rec.set_date_range(later.strftime("%Y-%m-%d"), (later + timedelta(days=1)).strftime("%Y-%m-%d"))
        assert first["id"] not in [r["id"] for r in rec.all_rows()]

    @allure.story("Pagination: Showing a-b of n, Next shows the following rows, Previous is disabled on page 1")
    def test_pagination(self, rec):
        a, b, n = rec.showing()
        if n <= 10:
            pytest.skip("fewer than 11 returns")
        assert (a, b) == (1, 10) and rec.row_count() == 10 and not rec.previous_enabled()
        page1 = [r["id"] for r in rec.all_rows()]
        rec.next_page()
        a2, b2, n2 = rec.showing()
        page2 = [r["id"] for r in rec.all_rows()]
        assert (a2, n2) == (11, n) and not set(page1) & set(page2) and rec.previous_enabled(), (a2, b2, n2)
        assert page2 == sorted(page2, reverse=True) and max(page2) < min(page1)

    @allure.story("Items per page 20 / 50 show that many rows (or all when fewer)")
    @pytest.mark.parametrize("size", [20, 50])
    def test_page_size(self, rec, size):
        n = rec.showing()[2]
        rec.set_page_size(size)
        assert rec.row_count() == min(size, n), (rec.row_count(), size, n)

    @allure.story("Jumping to a numbered page shows the matching range")
    def test_jump_to_page(self, rec):
        n = rec.showing()[2]
        if n <= 20:
            pytest.skip("fewer than 21 returns")
        rec.goto_page(3)
        assert rec.showing()[:2] == (21, min(30, n))

    @allure.story("Supplier + status + id search combine: every row satisfies all of them")
    def test_combined_filters(self, rec):
        row = rec.first_row()
        rec.search_supplier(row["supplier"])
        rec.choose_status(row["status"])
        rec.search_text(row["id"])
        rows = rec.all_rows()
        assert [r["id"] for r in rows] == [row["id"]], rows
        rec.choose_status("Cancelled" if row["status"] == "Returned" else "Returned")
        assert row["id"] not in [r["id"] for r in rec.all_rows()]
