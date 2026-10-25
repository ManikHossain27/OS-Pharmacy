"""Inventory Return to a supplier that is already in Advance (the pharmacy's own Advance supplier, QA_ADVANCE_SUPPLIER).

Rule (product owner): a return to any supplier moves that supplier's balance by the Final Price; for an Advance supplier
(negative balance) the Advance grows by the Final Price: New Balance = Previous - Final Price."""
from __future__ import annotations

import os

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from pages.supplier_list_page import SupplierListPage
from tests.inventory.return_module.helpers import TOL, batch_stock, checkout_and_complete, supplier_balance

ROUND = pytest.approx


@pytest.fixture()
def advance_supplier(page, pool) -> str:
    """The Advance supplier named by QA_ADVANCE_SUPPLIER (skips when absent or no longer in Advance)."""
    name = os.getenv("QA_ADVANCE_SUPPLIER")
    if not name:
        pytest.skip("QA_ADVANCE_SUPPLIER is not set")
    suppliers = SupplierListPage(page).open()
    if name not in suppliers.names():
        pytest.skip(f"supplier {name!r} is not in this pharmacy")
    if suppliers.balance(name) >= 0:
        pytest.skip(f"supplier {name!r} is not in Advance")
    return name


@allure.epic("Inventory")
@allure.feature("Inventory Return - Advance supplier")
class TestAdvanceSupplier:
    @allure.story("The checkout previews the Advance: Previous Balance negative, New Balance = Previous - Final Price")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("demurrage", [None, (10, "%"), (3, "Tk"), (100, "Tk")], ids=["none", "10pct", "tk3", "tk100"])
    def test_preview(self, page, pool, advance_supplier, demurrage):
        bal = supplier_balance(page, advance_supplier)
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[1], pool.batches[1], 5, "pc")
        ret.go_to_checkout()
        ret.select_supplier(advance_supplier)
        if demurrage:
            ret.set_demurrage(*demurrage)
        s = ret.summary()
        assert s["previous_balance"] == ROUND(bal, abs=TOL) and bal < 0, (bal, s)
        assert s["new_balance"] == ROUND(bal - s["final_price"], abs=TOL), s

    @allure.story("Completing a return to an Advance supplier grows that Advance by the Final Price; others are untouched")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("demurrage", [None, (10, "%")], ids=["none", "10pct"])
    def test_complete(self, page, pool, advance_supplier, demurrage):
        before = {n: supplier_balance(page, n) for n in (advance_supplier, pool.supplier)}
        stock = batch_stock(InventoryReturnPage(page).open(), pool.products[1], pool.batches[1])
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[1], pool.batches[1], 5, "pc")
        done = checkout_and_complete(ret, advance_supplier, demurrage)
        assert done.status in (200, 201), (done.status, done.body[:200])
        after = {n: supplier_balance(page, n) for n in before}
        assert after[advance_supplier] == ROUND(before[advance_supplier] - done.summary["final_price"], abs=TOL), (before, after)
        assert after[pool.supplier] == ROUND(before[pool.supplier], abs=TOL), (before, after)
        assert batch_stock(InventoryReturnPage(page).open(), pool.products[1], pool.batches[1]) == stock - 5

    @allure.story("Cancelling a return made to an Advance supplier gives the Advance back")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cancel_restores_advance(self, page, pool, advance_supplier):
        before = supplier_balance(page, advance_supplier)
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[1], pool.batches[1], 4, "pc")
        done = checkout_and_complete(ret, advance_supplier, (5, "%"))
        assert done.status in (200, 201), done.body[:200]
        assert supplier_balance(page, advance_supplier) == ROUND(before - done.summary["final_price"], abs=TOL)
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(rec.first_row()["id"])
        assert supplier_balance(page, advance_supplier) == ROUND(before, abs=TOL)

    @allure.story("A return from an Inventory Record to the Advance supplier (not the inventory's supplier)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_from_record(self, page, create, advance_supplier):
        saved = create("single_plain")
        assert saved.supplier != advance_supplier
        before = {n: supplier_balance(page, n) for n in (advance_supplier, saved.supplier)}
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        done = checkout_and_complete(ret, advance_supplier, (2, "%"))
        assert done.status in (200, 201), done.body[:200]
        after = {n: supplier_balance(page, n) for n in before}
        assert after[advance_supplier] == ROUND(before[advance_supplier] - done.summary["final_price"], abs=TOL), (before, after)
        assert after[saved.supplier] == ROUND(before[saved.supplier], abs=TOL), (before, after)
