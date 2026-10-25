"""Inventory Return started from an Inventory Record (row menu > Return Inventory, route /inventory-return?inventoryId=<id>).

Spec: "When returning from a specific Inventory Record, only products and available quantities belonging to that
inventory shall be returnable"; the cart is pre-loaded from that inventory; the supplier is chosen at checkout (the
product owner confirmed it is NOT pre-selected) and can be any supplier; a return is priced at the line's purchase price
(its final cost after discount and round-off, per piece).
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from tests.inventory.return_module.helpers import TOL, checkout_and_complete, expected_summary, supplier_balance

ROUND = pytest.approx
_RO: dict = {}


def _open(page, saved) -> InventoryReturnPage:
    return InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)


def _lines(saved):
    return saved.journey.inventory.lines


def _status(page, saved) -> str:
    rec = InventoryRecordPage(page).open()
    row = rec.row_by_inventory_id(saved.inventory_id)
    row.wait_for(state="visible", timeout=30_000)
    return rec.status_cell_text(row)


@pytest.fixture()
def ro(create):
    """One two-line fully paid Default inventory shared by the tests that do not consume its stock."""
    if "ro" not in _RO:
        _RO["ro"] = create("two_plain")
    return _RO["ro"]


# ---- the pre-loaded cart (nothing is completed) ---------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - from a record")
class TestRecordCart:
    @allure.story("The cart is pre-loaded with every line of the inventory, in pieces, at its purchase price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cart_preloaded(self, page, ro):
        ret = _open(page, ro)
        cart = ret.cart_lines()
        assert [l.batch for l in cart] == ro.journey.batches, cart
        for line, oracle in zip(cart, _lines(ro)):
            assert line.pieces == oracle.total_qty and line.unit == "pc", (line, oracle.total_qty)
            assert line.price == ROUND(oracle.final_line_cost, abs=0.02), (line.price, oracle.final_line_cost)
        assert ret.cart_total() == ROUND(sum(l.final_line_cost for l in _lines(ro)), abs=0.04)

    @allure.story("Each line's purchase price per piece is the inventory's final cost per piece")
    def test_price_per_piece(self, page, ro):
        for line, oracle in zip(_open(page, ro).cart_lines(), _lines(ro)):
            assert line.price_per_unit == ROUND(oracle.final_line_cost / oracle.total_qty, abs=0.006), line

    @allure.story("The supplier is NOT pre-selected at the Return Checkout (product owner), and Complete needs one")
    def test_supplier_not_preselected(self, page, ro):
        ret = _open(page, ro).go_to_checkout()
        assert not ret.supplier_preselected() and not ret.complete_enabled()

    @allure.story("Any supplier can receive the return, not only the inventory's own")
    def test_any_supplier_listed(self, page, ro, second_supplier):
        ret = _open(page, ro).go_to_checkout()
        opts = [o.lower() for o in ret.supplier_options()]
        assert any(ro.supplier.lower() in o for o in opts) and any(second_supplier.lower() in o for o in opts), opts

    @allure.story("Only this inventory's products are returnable: Company, Product and Batch are locked, so nothing else can be added")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_selectors_locked(self, page, ro):
        ret = _open(page, ro)
        assert all(ret.page.locator(f"#{f}").is_disabled() for f in ("companyId", "productId", "batchNo"))
        ret.delete_row(0)
        assert ret.page.locator("#productId").is_disabled(), "a removed line can be re-added only by reopening the return"

    @allure.story("A line's Return Qty cannot be raised above what is left in the batch")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_qty_above_remaining(self, page, ro):
        ret = _open(page, ro)
        remaining = ret.cart_lines()[0].pieces
        ret.edit_row(0)
        ret.set_qty(int(remaining) + 1)
        if ret.update_btn_visible():
            ret.update_cart()
        assert ret.cart_lines()[0].pieces <= remaining, ret.cart_lines()

    @allure.story("A partial quantity re-prices the line (edit 20 pcs to 5)")
    def test_partial_qty_price(self, page, ro):
        ret = _open(page, ro)
        ret.edit_row(0)
        ret.set_qty(5)
        ret.update_cart()
        line = ret.cart_lines()[0]
        o = _lines(ro)[0]
        assert line.pieces == 5 and line.price == ROUND(5 * o.final_line_cost / o.total_qty, abs=0.02), line

    @allure.story("A line can be returned by box")
    def test_by_box(self, page, ro):
        ret = _open(page, ro)
        ret.edit_row(0)
        ret.set_unit("Box")
        ret._per_box[ro.journey.batches[0]] = _lines(ro)[0].qty_per_box   # the cart shows boxes only
        ret.set_qty(1)
        ret.update_cart()
        line = ret.cart_lines()[0]
        o = _lines(ro)[0]
        assert line.unit == "box" and line.qty == 1 and line.pieces == o.qty_per_box, line
        assert line.price == ROUND(o.qty_per_box * o.final_line_cost / o.total_qty, abs=0.03), line

    @allure.story("A line can be removed so only part of the inventory is returned")
    def test_remove_a_line(self, page, ro):
        ret = _open(page, ro)
        ret.delete_row(0)
        assert [l.batch for l in ret.cart_lines()] == [ro.journey.batches[1]]
        assert ret.cart_total() == ROUND(_lines(ro)[1].final_line_cost, abs=0.04)

    @allure.story("Leaving without completing changes nothing: opening the return again shows the full cart")
    def test_abandoned_return(self, page, ro):
        ret = _open(page, ro)
        ret.delete_row(0)
        again = _open(page, ro)
        assert len(again.cart_lines()) == 2


# ---- completing from a record ---------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - from a record")
class TestRecordComplete:
    @allure.story("A full return of the inventory empties its batches, credits the supplier, and is recorded")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_full_return(self, page, create, catalogue):
        saved = create("two_plain")
        before = supplier_balance(page, saved.supplier)
        ret = _open(page, saved)
        done = checkout_and_complete(ret, saved.supplier)
        total = sum(l.final_line_cost for l in _lines(saved))
        assert done.status in (200, 201), (done.status, done.body[:300])
        assert done.cart_total == ROUND(total, abs=0.04)
        assert supplier_balance(page, saved.supplier) == ROUND(before - done.summary["final_price"], abs=TOL)
        form = InventoryReturnPage(page).open()
        for product, batch in zip(catalogue[:2], saved.journey.batches):
            form.select_product(product)
            assert batch not in [b["batch"] for b in form.batch_options()], f"{batch} still has stock after a full return"
        row = InventoryReturnRecordPage(page).open().first_row()
        assert row["status"] == "Returned" and row["items"].startswith("2")

    @allure.story("After a full return the inventory's record shows Returned")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_record_status_full(self, page, create):
        saved = create("two_plain")
        checkout_and_complete(_open(page, saved), saved.supplier)
        assert "return" in _status(page, saved).lower(), _status(page, saved)

    @allure.story("A partial return (one line, fewer pieces) deducts only that quantity and the record shows Returned")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_partial_return(self, page, create, catalogue):
        saved = create("two_plain")
        before = supplier_balance(page, saved.supplier)
        ret = _open(page, saved)
        ret.delete_row(1)
        ret.edit_row(0)
        ret.set_qty(5)
        ret.update_cart()
        o = _lines(saved)[0]
        done = checkout_and_complete(ret, saved.supplier, (10, "%"))
        exp = expected_summary(round(5 * o.final_line_cost / o.total_qty, 2), (10, "%"))
        assert done.status in (200, 201), done.body[:300]
        assert done.summary["final_price"] == ROUND(exp["final_price"], abs=TOL), (done.summary, exp)
        assert supplier_balance(page, saved.supplier) == ROUND(before - exp["final_price"], abs=TOL)
        again = _open(page, saved).cart_lines()
        assert [l.pieces for l in again] == [o.total_qty - 5, _lines(saved)[1].total_qty], again
        assert "return" in _status(page, saved).lower(), _status(page, saved)

    @allure.story("The remainder of a partly returned inventory can be returned later; then nothing is left")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_return_the_remainder(self, page, create):
        saved = create("two_plain")
        ret = _open(page, saved)
        ret.delete_row(1)
        ret.edit_row(0)
        ret.set_qty(8)
        ret.update_cart()
        checkout_and_complete(ret, saved.supplier)
        before = supplier_balance(page, saved.supplier)
        ret = _open(page, saved)
        cart = ret.cart_lines()
        assert [l.pieces for l in cart] == [_lines(saved)[0].total_qty - 8, _lines(saved)[1].total_qty]
        done = checkout_and_complete(ret, saved.supplier)
        assert supplier_balance(page, saved.supplier) == ROUND(before - done.summary["final_price"], abs=TOL)
        left = _open(page, saved)
        assert left.cart_lines() == [] or all(l.pieces == 0 for l in left.cart_lines()), left.cart_lines()

    @allure.story("A fully returned inventory has nothing left to return: the cart opens empty and checkout is disabled")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_nothing_left_to_return(self, page, create):
        saved = create("single_plain")
        checkout_and_complete(_open(page, saved), saved.supplier)
        ret = _open(page, saved)
        assert ret.cart_lines() == [] and not ret.checkout_enabled(), ret.cart_lines()

    @allure.story("The return can go to a supplier other than the inventory's; the original supplier is untouched")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_to_a_different_supplier(self, page, create, second_supplier):
        saved = create("two_plain")
        target = next(n for n in (second_supplier, saved.supplier) if n.lower() != saved.supplier.lower())
        a0, b0 = supplier_balance(page, saved.supplier), supplier_balance(page, target)
        done = checkout_and_complete(_open(page, saved), target, (5, "%"))
        assert supplier_balance(page, target) == ROUND(b0 - done.summary["final_price"], abs=TOL)
        assert supplier_balance(page, saved.supplier) == ROUND(a0, abs=TOL)
        assert InventoryReturnRecordPage(page).open().first_row()["supplier"].lower().startswith(target.lower()[:8])

    @allure.story("Returning a Due inventory (nothing paid) credits the supplier the same way")
    def test_due_inventory(self, page, create):
        saved = create("two_plain", paid_ratio=0.0, choice="Due & Buy")
        before = supplier_balance(page, saved.supplier)
        done = checkout_and_complete(_open(page, saved), saved.supplier)
        assert supplier_balance(page, saved.supplier) == ROUND(before - done.summary["final_price"], abs=TOL)

    @allure.story("A discounted inventory is returned at its discounted cost (final cost per piece), not the list price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_discounted_inventory(self, page, create):
        saved = create("two_plain", discount=(10, "%"))
        cart = _open(page, saved).cart_lines()
        for line, o in zip(cart, _lines(saved)):
            assert line.price == ROUND(o.final_line_cost, abs=0.02), (line.price, o.final_line_cost, o.btp_vat_per_box * o.box_qty)
        assert sum(l.price for l in cart) < sum(o.btp_vat_per_box * o.box_qty for o in _lines(saved))

    @allure.story("An inventory with Free Qty: free pieces are returnable too, at the same per-piece purchase price as the batch")
    def test_free_qty_inventory(self, page, create):
        saved = create("single_free")
        o = _lines(saved)[0]
        line = _open(page, saved).cart_lines()[0]
        assert line.pieces == o.total_qty + o.free_qty, (line, o.total_qty, o.free_qty)
        assert line.price == ROUND((o.total_qty + o.free_qty) * o.final_line_cost / o.total_qty, abs=0.05), (line.price, o.final_line_cost)

    @allure.story("A Cancelled inventory cannot be returned (nothing is in stock any more)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_cancelled_inventory(self, page, create):
        saved = create("single_plain")
        InventoryRecordPage(page).open().cancel_inventory(saved.inventory_id)
        rec = InventoryRecordPage(page).open()
        rec.reset_filters_btn.click()
        page.wait_for_timeout(1500)
        rec.wait_loaded()
        rec.choose_filter("status", "Cancelled")
        row = rec.row_by_inventory_id(saved.inventory_id)
        if "Return Inventory" not in rec.open_row_menu(row):
            return
        item = page.locator(".ant-dropdown:not(.ant-dropdown-hidden) li", has_text="Return Inventory").first
        if "disabled" in (item.get_attribute("class") or "") or item.get_attribute("aria-disabled") == "true":
            return
        item.dispatch_event("click")
        page.wait_for_timeout(5000)
        ret = InventoryReturnPage(page)
        assert ret.cart_lines() == [] and not ret.checkout_enabled(), ret.cart_lines()

    @allure.story("Two tabs returning the same stock: the second return is refused, nothing goes negative")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_stale_second_tab(self, page, context, create):
        saved = create("single_plain")
        tab = context.new_page()
        try:
            second = _open(tab, saved)
            second.go_to_checkout()
            second.select_supplier(saved.supplier)
            checkout_and_complete(_open(page, saved), saved.supplier)
            before = supplier_balance(page, saved.supplier)
            status, body = second.complete()
            assert status is None or status >= 400 or "error" in second.toast_text().lower(), (status, body[:300])
        finally:
            tab.close()
        assert supplier_balance(page, saved.supplier) == ROUND(before, abs=TOL), "the stale return credited the supplier twice"


# ---- other modes ----------------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - from a record")
class TestRecordOtherModes:
    @allure.story("TP/VAT and Opening Stock inventories are returned from their record like Default ones")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_full_return(self, page, mode_saved):
        saved = mode_saved
        before = supplier_balance(page, saved.supplier)
        ret = _open(page, saved)
        cart = ret.cart_lines()
        assert [l.batch for l in cart] == saved.journey.batches and ret.cart_total() == ROUND(saved.final, abs=1.01), cart
        done = checkout_and_complete(ret, saved.supplier, (5, "%"))
        assert done.status in (200, 201), done.body[:300]
        assert supplier_balance(page, saved.supplier) == ROUND(before - done.summary["final_price"], abs=TOL)
        assert InventoryReturnRecordPage(page).open().first_row()["status"] == "Returned"

    @allure.story("A TP/VAT / Opening Stock inventory can be returned in part")
    def test_partial_return(self, page, mode_saved):
        saved = mode_saved
        before = supplier_balance(page, saved.supplier)
        ret = _open(page, saved)
        ret.delete_row(1)
        ret.edit_row(0)
        ret.set_qty(1)
        ret.update_cart()
        done = checkout_and_complete(ret, saved.supplier)
        assert supplier_balance(page, saved.supplier) == ROUND(before - done.summary["final_price"], abs=TOL)
