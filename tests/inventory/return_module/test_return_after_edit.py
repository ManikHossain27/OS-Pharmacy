"""Inventory Return after the inventory was edited (product owner): an edit recalculates the inventory's purchase price and
the other figures, and the return is then priced at the NEW purchase price. Retail / wholesale edits do not change the
purchase price, so they must not change the return price."""
from __future__ import annotations

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage
from tests.inventory.edit_module.helpers import edit_fields, pay_and_update, reopen_edit
from tests.inventory.return_module.helpers import TOL, checkout_and_complete, supplier_balance

ROUND = pytest.approx


def _edit(page, saved, **fields):
    record = InventoryRecordPage(page)
    edit = reopen_edit(page, record, saved.inventory_id)
    edit_fields(edit, 0, **fields)
    result = pay_and_update(edit, "full", saved.paid)
    assert result.status in (200, 201), (result.status, result.body[:200])
    return result


def _return_cart(page, saved):
    return InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)


@allure.epic("Inventory")
@allure.feature("Inventory Return - after Edit Inventory")
class TestReturnAfterEditPrice:
    @allure.story("After the purchase price is edited the return cart is priced at the new price")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("new_price", [40, 12.5], ids=["higher", "lower"])
    def test_purchase_price_edit(self, page, create, new_price):
        saved = create("two_plain")
        old_total = saved.final
        result = _edit(page, saved, price_per_box=new_price)
        ret = _return_cart(page, saved)
        lines = ret.cart_lines()
        assert ret.cart_total() == ROUND(result.final, abs=0.51), (ret.cart_total(), result.final, old_total)
        assert ret.cart_total() != ROUND(old_total, abs=0.5), "the return still uses the old purchase price"
        spec = saved.journey.specs[0]
        per_box = lines[0].price / (lines[0].pieces / saved.journey.lines[0].qty_per_box)
        assert per_box == ROUND(new_price, abs=0.03), (per_box, new_price, lines[0])

    @allure.story("A return after a price edit moves the supplier balance by the edited Final Price")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_balance_after_price_edit(self, page, create):
        saved = create("two_plain")
        _edit(page, saved, price_per_box=40)
        bal = supplier_balance(page, saved.supplier)
        done = checkout_and_complete(_return_cart(page, saved), saved.supplier, (10, "%"))
        assert done.status in (200, 201), done.body[:200]
        assert supplier_balance(page, saved.supplier) == ROUND(bal - done.summary["final_price"], abs=TOL)

    @allure.story("Retail / wholesale price edits do not change the purchase price used for the return")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_retail_wholesale_edit_keeps_return_price(self, page, create):
        saved = create("two_plain")
        _edit(page, saved, retail_price=75, wholesale_price=55)
        ret = _return_cart(page, saved)
        assert ret.cart_total() == ROUND(saved.final, abs=0.51), (ret.cart_total(), saved.final)

    @allure.story("A quantity edit and a price edit together: the return is the edited quantity at the edited price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_quantity_and_price_edit(self, page, create):
        saved = create("two_plain")
        result = _edit(page, saved, box_qty=5, price_per_box=40)
        ret = _return_cart(page, saved)
        assert ret.cart_total() == ROUND(result.final, abs=0.51), (ret.cart_total(), result.final)
        assert ret.cart_lines()[0].pieces == 5 * saved.journey.lines[0].qty_per_box

    @allure.story("Edit twice (price up then down): the return uses the latest purchase price")
    def test_two_price_edits(self, page, create):
        saved = create("two_plain")
        _edit(page, saved, price_per_box=60)
        result = _edit(page, saved, price_per_box=15)
        ret = _return_cart(page, saved)
        assert ret.cart_total() == ROUND(result.final, abs=0.51), (ret.cart_total(), result.final)
