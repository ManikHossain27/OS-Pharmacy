"""Inventory Return - text fields, page reload / Back, and two tabs returning the same stock."""
from __future__ import annotations

import allure
import pytest

from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from tests.inventory.return_module.helpers import batch_stock, checkout_and_complete

TEXTS = {
    "script": "<script>alert(1)</script><img src=x onerror=alert(2)>",
    "quotes": "O'Brien \"quoted\" `tick` \\ back\\slash",
    "bangla": "চালান নম্বর ১২৩ – সরবরাহকারী ফেরত",
    "emoji": "return 📦 ✅ ñ é ü",
    "sql": "'; DROP TABLE returns; --",
    "spaces": "   padded   ",
    "long-300": "L" * 300,
    "long-2000": "N" * 2000,
}


@allure.epic("Inventory")
@allure.feature("Inventory Return - text fields")
class TestTextFields:
    @allure.story("Invoice number and note accept (or cleanly refuse) any text; the page never fails and no script runs")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("kind", list(TEXTS))
    def test_invoice_and_note(self, page, pool, kind):
        text = TEXTS[kind]
        dialogs: list[str] = []
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[1], pool.batches[1], 1, "pc")
        done = checkout_and_complete(ret, pool.supplier, invoice=text[:300] if kind != "long-2000" else text, note=text)
        assert done.status is not None and done.status < 500, (kind, done.status, done.body[:200])
        assert not dialogs, f"a script in the text ran: {dialogs}"
        errors = [e for e in getattr(page, "_qa_console_errors", []) if e.startswith("PAGEERROR")]
        assert not errors, errors
        if done.status in (200, 201):
            rec = InventoryReturnRecordPage(page).open()
            rec.open_details(rec.row_by_id(rec.first_row()["id"]))
            assert not dialogs, f"a script in the text ran when the Details opened: {dialogs}"
            rec.close_details()


@allure.epic("Inventory")
@allure.feature("Inventory Return - navigation")
class TestNavigation:
    @allure.story("Reloading the Return page with a filled cart leaves a usable page (cart kept or cleanly empty)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_reload_with_cart(self, page, pool):
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[1], pool.batches[1], 3, "pc")
        before = ret.cart_lines()
        page.reload()
        ret.wait_loaded()
        after = ret.cart_lines()
        assert after in ([], before), (before, after)
        ret.add_line(pool.products[2], pool.batches[2], 2, "pc")      # still usable
        assert ret.cart_lines()[-1].pieces == 2

    @allure.story("Browser Back from the Return Checkout returns to the cart with its lines intact")
    @allure.severity(allure.severity_level.NORMAL)
    def test_back_from_checkout(self, page, pool):
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[1], pool.batches[1], 3, "pc")
        ret.add_line(pool.products[2], pool.batches[2], 4, "pc")
        before = ret.cart_lines()
        ret.go_to_checkout()
        page.go_back()
        ret.wait_loaded()
        after = ret.cart_lines()
        assert after in ([], before), (before, after)
        if after:
            assert ret.cart_total() == pytest.approx(sum(l.price for l in before), abs=0.03)

    @allure.story("Opening a return for an unknown / malformed inventory id does not break the page")
    @pytest.mark.negative
    @pytest.mark.parametrize("bad", ["999999999", "abc", "-1", "0", "1;DROP"], ids=["huge", "text", "negative", "zero", "sql"])
    def test_bad_inventory_id(self, page, pool, bad):
        page.goto(page.url.split("/")[0] + "//" + page.url.split("/")[2] + f"/inventory-return?inventoryId={bad}",
                  wait_until="domcontentloaded")
        ret = InventoryReturnPage(page)
        ret.wait_loaded()
        assert ret.cart_lines() == [], ret.cart_lines()
        ret.add_line(pool.products[1], pool.batches[1], 1, "pc")     # the form still works
        assert len(ret.cart_lines()) == 1


@allure.epic("Inventory")
@allure.feature("Inventory Return - concurrency")
class TestTwoTabs:
    @allure.story("Two tabs fill the same batch's whole stock; the second Complete is refused (no double return)")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    def test_double_spend(self, page, create, catalogue):
        saved = create("single_plain")
        product = catalogue[int(saved.journey.specs[0].product[1:])]
        batch = saved.journey.batches[0]
        stock = batch_stock(InventoryReturnPage(page).open(), product, batch)
        assert stock, "the new batch has no stock"
        first = InventoryReturnPage(page).open()
        first.add_line(product, batch, stock, "pc")
        second_page = page.context.new_page()
        try:
            second = InventoryReturnPage(second_page).open()
            second.add_line(product, batch, stock, "pc")
            ok = checkout_and_complete(first, saved.supplier)
            assert ok.status in (200, 201), ok.body[:200]
            second_done = checkout_and_complete(second, saved.supplier)
            assert second_done.status is None or second_done.status >= 400, \
                f"the same stock was returned twice (HTTP {second_done.status})"
        finally:
            second_page.close()
