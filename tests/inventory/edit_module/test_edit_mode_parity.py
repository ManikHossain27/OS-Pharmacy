"""Edit Inventory for TP/VAT and Opening Stock records - the same checks the Default suite makes
(``test_edit_inventory.py`` / ``test_edit_matrix.py``), plus each mode's own price fields.

Expected amounts are read from the cart and the edit checkout (the mode oracles already verify the create flow), so a
case passes when what was saved is what the edit screens showed.  Combinations of starting state, edit and payment
for these modes are in ``test_edit_combinations.py``.
Serial, headed: ``pytest tests/inventory/edit_module/test_edit_mode_parity.py --headed-run``.
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_edit_page import EDIT_CHECKOUT_URL
from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.edit_module.conftest import _OTHER_MODES
from tests.inventory.edit_module.helpers import (
    add_product, edit_fields, edit_line, history_changes, num, pay_and_update, record_row, reopen_edit, update)
from utils.inventory_scenarios import LineSpec

@pytest.fixture()
def mode_edit(page, mode_saved):
    return reopen_edit(page, InventoryRecordPage(page), mode_saved.inventory_id)


def _ok(result) -> None:
    status = result.status if hasattr(result, "status") else result[0]
    body = result.body if hasattr(result, "body") else result[1]
    assert status == 200, f"Update Inventory failed: HTTP {status} {str(body)[:300]}"


def _record(page) -> InventoryRecordPage:
    return InventoryRecordPage(page)


@allure.epic("Inventory")
@allure.feature("Edit Inventory - TP/VAT and Opening Stock")
class TestModeLineFields:
    @allure.story("A changed line field is persisted by Update Inventory")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("key,value", [("retail_price", 75), ("wholesale_price", 55), ("min_qty", 9),
                                           ("rack_no", "Z9"), ("free_qty", 1)])
    def test_field_persisted(self, mode_saved, mode_edit, page, key, value):
        edit_fields(mode_edit, 0, **{key: value})
        _ok(update(mode_edit))
        again = reopen_edit(page, _record(page), mode_saved.inventory_id)
        again.cart.edit_cart_row(again.cart.cart_row(0))
        got = again.cart.form_snapshot()[key]
        assert got == str(value) or num(got) == pytest.approx(num(str(value)), abs=0.011), \
            f"{key}: saved {value!r} but the edit form reloads {got!r}"

    @allure.story("A new Batch No is persisted")
    def test_batch_no_persisted(self, mode_saved, mode_edit, flow, page):
        batch = flow.next_batch("E")
        edit_fields(mode_edit, 0, batch_no=batch)
        _ok(update(mode_edit))
        dlg = _record(page).open().open_details_for(mode_saved.inventory_id).wait_loaded()
        assert dlg.item_row_by_batch(batch), f"batch {batch} missing from Details: {dlg.item_rows()}"

    @allure.story("Reusing another line's Batch No is refused")
    @pytest.mark.negative
    def test_duplicate_batch_refused(self, mode_saved, mode_edit):
        edit_fields(mode_edit, 0, batch_no=mode_saved.journey.batches[1])
        status, _ = update(mode_edit)
        assert status != 200, f"a Batch No already used by another line was accepted: {status}"

    @allure.story("An Expiry Date set on a line shows in the cart's Exp date column")
    def test_expiry_date_in_cart(self, mode_edit):
        inv = mode_edit.cart
        inv.edit_cart_row(inv.cart_row(0))
        inv.set_expiry_date(1, "Jan", 2031)
        inv.submit_cart_item()
        assert "2031" in inv.cart_rows()[0]["Exp date"], inv.cart_rows()[0]

    @allure.story("Both lines can be edited in one session and the Record bills the checkout's Final Price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_edit_both_lines(self, mode_saved, mode_edit, page):
        edit_line(mode_edit, 0, 4)
        edit_line(mode_edit, 1, 6)
        total = mode_edit.cart.cart_total_price()
        result = pay_and_update(mode_edit, "full", mode_saved.paid)
        _ok(result)
        assert result.final == pytest.approx(total, abs=0.51)
        assert num(record_row(_record(page), mode_saved.inventory_id)["bill"]) == pytest.approx(result.final, abs=0.51)


@allure.epic("Inventory")
@allure.feature("Edit Inventory - TP/VAT and Opening Stock")
class TestModeCartStructure:
    @allure.story("A new product added in Edit Inventory is saved with the record")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_add_product(self, mode, mode_saved, mode_edit, flow, page):
        extra = _OTHER_MODES[mode][2]["three_plain_free_plain"][2]
        add_product(mode_edit, mode, extra, flow.next_batch("E"))
        assert mode_edit.cart.total_items() == 3
        total = mode_edit.cart.cart_total_price()
        result = pay_and_update(mode_edit, "full", mode_saved.paid)
        _ok(result)
        row = record_row(_record(page), mode_saved.inventory_id)
        assert "3" in row["qty"] and num(row["bill"]) == pytest.approx(total, abs=0.51), (row, total)

    @allure.story("A product already in the cart cannot be added again in Edit Inventory")
    @pytest.mark.negative
    def test_duplicate_product_refused(self, mode_saved, mode_edit, flow):
        spec = mode_saved.journey.specs[0]
        added, msgs = mode_edit.cart.try_add_line(LineSpec(spec.product, box_qty=2, btp_vat_per_box=spec.btp_vat_per_box,
                                                           retail=spec.retail, wholesale=spec.wholesale,
                                                           min_qty=spec.min_qty, rack=spec.rack), flow.next_batch("E"))
        assert not added and mode_edit.cart.total_items() == 2, msgs

    @allure.story("Deleting a line and updating removes it from the record")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_line_saved(self, mode_saved, mode_edit, page):
        mode_edit.cart.delete_cart_row(mode_edit.cart.cart_row(0))
        total = mode_edit.cart.cart_total_price()
        _ok(pay_and_update(mode_edit, "full", mode_saved.paid))
        row = record_row(_record(page), mode_saved.inventory_id)
        assert "1" in row["qty"] and num(row["bill"]) == pytest.approx(total, abs=0.51), row

    @allure.story("An edited cart with no lines cannot be taken to checkout")
    @pytest.mark.negative
    def test_empty_cart_cannot_checkout(self, mode_edit):
        inv = mode_edit.cart
        while inv.cart_row_count():
            inv.delete_cart_row(inv.cart_row(0))
        assert not inv.go_to_checkout_btn.is_enabled(), "Go to Inventory Checkout is enabled for an empty cart"

    @allure.story("A line cannot be changed to Box Qty 0")
    @pytest.mark.negative
    def test_box_qty_zero_rejected(self, mode_edit):
        inv = mode_edit.cart
        inv.edit_cart_row(inv.cart_row(0))
        inv.type_value("box_qty", "0")
        inv.click(inv.submit_button(), description="Save Changes")
        mode_edit.page.wait_for_timeout(1500)
        assert num(inv.cart_rows()[0]["Box Qty"]) != 0, "BUG-INV-030: Box Qty 0 was accepted when editing a line"

    @allure.story("Large Box Qty is saved and billed as the checkout showed")
    def test_large_box_qty(self, mode_saved, mode_edit, page):
        edit_line(mode_edit, 0, 1000)
        total = mode_edit.cart.cart_total_price()
        result = pay_and_update(mode_edit, "full", mode_saved.paid)
        _ok(result)
        assert num(record_row(_record(page), mode_saved.inventory_id)["bill"]) == pytest.approx(total, abs=0.51)


@allure.epic("Inventory")
@allure.feature("Edit Inventory - TP/VAT and Opening Stock")
class TestModeCheckout:
    @allure.story("The edit checkout keeps the saved supplier and type")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_checkout_keeps_supplier_and_type(self, mode_saved, mode_edit, page):
        co = mode_edit.go_to_checkout()
        assert EDIT_CHECKOUT_URL.search(page.url), page.url
        assert co.inventory_type() == "Purchase"
        assert mode_saved.supplier.lower() in page.locator("body").inner_text().lower()

    @allure.story("Checkout totals follow the edited cart: Final Price is the Total Price rounded")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_checkout_totals_after_box_qty_change(self, mode_edit):
        edit_line(mode_edit, 0, 5)
        total = mode_edit.cart.cart_total_price()
        s = mode_edit.go_to_checkout().summary()
        assert s["total_price"] == pytest.approx(total, abs=0.011) and s["final_price"] == pytest.approx(total, abs=0.51), s

    @allure.story("The inventory type is read-only in the edit checkout")
    @pytest.mark.negative
    def test_type_is_read_only(self, mode_edit):
        select = mode_edit.go_to_checkout().inventory_type_select
        assert "ant-select-disabled" in (select.root.get_attribute("class") or ""), \
            "Inventory Type is editable in the edit checkout, but the server refuses a type change (BUG-INV-037)"

    @allure.story("An Invoice Number entered in the edit checkout is saved and pre-loaded next time")
    def test_invoice_number_persisted(self, mode_saved, mode_edit, page):
        co = mode_edit.go_to_checkout()
        co.set_invoice_number("EDIT-INV-77")
        status, body = mode_edit.update_capturing_response(co)
        assert status == 200, f"update failed: {status} {body[:300]}"
        again = reopen_edit(page, _record(page), mode_saved.inventory_id).go_to_checkout()
        assert again.invoice_number_input.input_value() == "EDIT-INV-77"

    @allure.story("The payment dialog shows the right bill / paid / shortfall amounts on edit")
    def test_payment_dialog_amounts(self, mode_edit):
        co = mode_edit.go_to_checkout()
        final = co.summary()["final_price"]
        co.set_paid_amount(100)
        mode_edit.update_capturing_response(co, choice="Due & Buy")
        snap = co.last_payment_dialog or {}
        assert snap.get("kind") == "less", snap
        assert snap.get("bill") == pytest.approx(final, abs=0.011) and snap.get("paid") == pytest.approx(100, abs=0.011), snap
        assert snap.get("gap") == pytest.approx(final - 100, abs=0.011), snap


@allure.epic("Inventory")
@allure.feature("Edit Inventory - TP/VAT and Opening Stock")
class TestModeHistoryAndNavigation:
    @allure.story("A record that was never edited has no changes in its Edit History")
    def test_history_empty_before_edit(self, mode_saved, page):
        count, text = history_changes(_record(page), mode_saved.inventory_id)
        assert count == 0, text[-400:]

    @allure.story("Two updates give two history entries and the second figures win")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_second_edit(self, mode_saved, mode_edit, page):
        edit_line(mode_edit, 0, 5)
        _ok(pay_and_update(mode_edit, "full", mode_saved.paid))
        again = reopen_edit(page, _record(page), mode_saved.inventory_id)
        edit_line(again, 0, 7)
        second = pay_and_update(again, "full", mode_saved.paid)
        _ok(second)
        count, text = history_changes(_record(page), mode_saved.inventory_id)
        assert count == 2, text[-400:]
        assert num(record_row(_record(page), mode_saved.inventory_id)["bill"]) == pytest.approx(second.final, abs=0.51)

    @allure.story("Leaving Edit Inventory without Update changes nothing")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_abandoned_edit_changes_nothing(self, mode_saved, mode_edit, page):
        edit_line(mode_edit, 0, 9)
        row = record_row(_record(page), mode_saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(mode_saved.final, abs=0.51), row
        assert history_changes(_record(page), mode_saved.inventory_id)[0] == 0

    @allure.story("Edit Cart in the edit checkout returns to the edit cart with the changes intact")
    def test_edit_cart_from_edit_checkout(self, mode_edit):
        edit_line(mode_edit, 0, 5)
        inv = mode_edit.go_to_checkout().edit_cart()
        assert inv.total_items() == 2 and num(inv.cart_rows()[0]["Box Qty"]) == 5

    @allure.story("A cancelled inventory cannot be edited: the row menu must not offer Edit Inventory")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_cancelled_record_not_editable(self, mode_saved, page):
        record = _record(page).open()
        record.cancel_inventory(mode_saved.inventory_id)
        page.reload()
        record.wait_loaded()
        record.choose_filter("status", "Cancelled")
        items = record.open_row_menu(record.row_by_inventory_id(mode_saved.inventory_id))
        assert "Edit Inventory" not in items, f"a Cancelled inventory still offers Edit Inventory: {items}"


# ---- each mode's own price fields ----------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - TP/VAT and Opening Stock")
class TestTpVatPrices:
    @pytest.fixture()
    def tpvat_saved(self, create_in):
        return create_in("TP/VAT", "two_plain")

    @pytest.fixture()
    def tpvat_edit(self, page, tpvat_saved):
        return reopen_edit(page, _record(page), tpvat_saved.inventory_id)

    @allure.story("A changed TP/Box or VAT/Box is persisted and reprices the line, the cart total and the Record")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("key,value", [("tp_per_box", 90), ("vat_per_box", 7), ("tp_per_box", 55)],
                             ids=["tp_up", "vat_up", "tp_down"])
    def test_tp_vat_field_reprices(self, tpvat_saved, tpvat_edit, page, key, value):
        before = tpvat_edit.cart.cart_total_price()
        edit_fields(tpvat_edit, 0, **{key: value})
        total = tpvat_edit.cart.cart_total_price()
        assert total != pytest.approx(before, abs=0.011), f"{key}={value} did not reprice the cart ({before} -> {total})"
        result = pay_and_update(tpvat_edit, "full", tpvat_saved.paid)
        _ok(result)
        assert result.final == pytest.approx(total, abs=0.51)
        assert num(record_row(_record(page), tpvat_saved.inventory_id)["bill"]) == pytest.approx(result.final, abs=0.51)
        again = reopen_edit(page, _record(page), tpvat_saved.inventory_id)
        again.cart.edit_cart_row(again.cart.cart_row(0))
        assert num(again.cart.form_snapshot()[key]) == pytest.approx(value, abs=0.011)

    @allure.story("TP and VAT edited together bill the sum per box")
    def test_tp_and_vat_together(self, tpvat_saved, tpvat_edit):
        edit_fields(tpvat_edit, 0, tp_per_box=80, vat_per_box=10)
        row = tpvat_edit.cart.cart_rows()[0]
        assert num(row["Total Price"]) == pytest.approx(num(row["Box Qty"]) * 90, abs=0.02), row


@allure.epic("Inventory")
@allure.feature("Edit Inventory - TP/VAT and Opening Stock")
class TestOpeningStockPrices:
    @pytest.fixture()
    def opening_saved(self, create_in):
        return create_in("Opening Stock", "two_plain")

    @pytest.fixture()
    def opening_edit(self, page, opening_saved):
        return reopen_edit(page, _record(page), opening_saved.inventory_id)

    @allure.story("Changing the Opening Stock % reprices the line from its Retail Price")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("pct", [20, 5], ids=["pct_20", "pct_5"])
    def test_opening_percent_reprices(self, opening_saved, opening_edit, page, pct):
        before = opening_edit.cart.cart_total_price()
        edit_fields(opening_edit, 0, opening_stock_percent=pct)
        total = opening_edit.cart.cart_total_price()
        assert total != pytest.approx(before, abs=0.011), f"{pct}% did not reprice the cart ({before} -> {total})"
        result = pay_and_update(opening_edit, "full", opening_saved.paid)
        _ok(result)
        assert num(record_row(_record(page), opening_saved.inventory_id)["bill"]) == pytest.approx(result.final, abs=0.51)

    @allure.story("A manual BTP+VAT/Box override is persisted and billed")
    def test_manual_btp_override(self, opening_saved, opening_edit, page):
        edit_fields(opening_edit, 0, price_per_box=70)
        row = opening_edit.cart.cart_rows()[0]
        assert num(row["Total Price"]) == pytest.approx(num(row["Box Qty"]) * 70, abs=0.02), row
        _ok(pay_and_update(opening_edit, "full", opening_saved.paid))
        again = reopen_edit(page, _record(page), opening_saved.inventory_id)
        again.cart.edit_cart_row(again.cart.cart_row(0))
        assert num(again.cart.form_snapshot()["price_per_box"]) == pytest.approx(70, abs=0.011)

    @allure.story("Changing the Retail Price re-derives BTP+VAT/Box while it is system-calculated")
    def test_retail_price_rederives_btp(self, opening_saved, opening_edit):
        before = opening_edit.cart.cart_total_price()
        edit_fields(opening_edit, 0, retail_price=100)
        assert opening_edit.cart.cart_total_price() != pytest.approx(before, abs=0.011), \
            "a new Retail Price did not re-derive the Opening Stock BTP+VAT/Box"
