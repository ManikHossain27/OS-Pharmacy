"""Edit Inventory - the edits beyond a Box Qty change: every line field, cart structure, discount, payment,
supplier / type, Edit History and starting states.

Each test creates its own inventory (``create`` / ``saved``) and edits that one.  After an update the record is
re-opened from the server, so what is asserted is what was PERSISTED, not what the form still shows.
Serial, headed: ``pytest tests/inventory/edit_module --headed-run``.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.edit_module.helpers import (
    bill, edit_fields, edit_line, final_price, history_changes, num, record_row, reopen_edit, update)
from utils.inventory_scenarios import LineSpec

P2 = LineSpec("P2", box_qty=1, btp_vat_per_box=80, retail=120, wholesale=100, min_qty=0, rack="C3")


def _ok(result) -> None:
    status, body = result
    assert status == 200, f"Update Inventory failed: HTTP {status} {str(body)[:300]}"


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditLineFields:
    """Every editable line field is saved: change it, Update, re-open Edit Inventory and read it back."""

    @pytest.mark.parametrize("key,value", [
        pytest.param("retail_price", 75, id="retail_price"),
        pytest.param("wholesale_price", 55, id="wholesale_price"),
        pytest.param("min_qty", 9, id="min_qty"),
        pytest.param("rack_no", "Z9", id="rack"),
        pytest.param("free_qty", 1, id="free_qty"),
        pytest.param("qty_per_box", 12, id="qty_per_box"),
        pytest.param("price_per_box", 40, id="btp_vat_per_box"),
    ])
    @allure.story("A changed line field is persisted by Update Inventory")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_field_persisted(self, edit, saved, record, page, key, value):
        edit_fields(edit, 0, **{key: value})
        _ok(update(edit))
        again = reopen_edit(page, record, saved.inventory_id)
        again.cart.edit_cart_row(again.cart.cart_row(0))
        got = again.cart.form_snapshot()[key]
        assert got == str(value) or num(got) == pytest.approx(num(str(value)), abs=0.011), \
            f"{key}: saved {value!r} but the edit form reloads {got!r}"

    @allure.story("A changed BTP+VAT/Box reprices the line, the cart total and the Record's bill")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_price_change_flows_to_record(self, edit, saved, record):
        specs = saved.journey.specs
        edit_fields(edit, 0, price_per_box=40)
        new_total = round(specs[0].box_qty * 40 + specs[1].box_qty * specs[1].btp_vat_per_box, 2)
        assert edit.cart.cart_total_price() == pytest.approx(new_total, abs=0.011)
        _ok(update(edit))
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(final_price(new_total), abs=0.51)

    @allure.story("A new Batch No is persisted")
    def test_batch_no_persisted(self, edit, saved, record, page, flow):
        batch = flow.next_batch("E")
        edit_fields(edit, 0, batch_no=batch)
        _ok(update(edit))
        dlg = record.open().open_details_for(saved.inventory_id).wait_loaded()
        assert dlg.item_row_by_batch(batch), f"batch {batch} missing from Details: {dlg.item_rows()}"

    @allure.story("Reusing another line's Batch No is refused")
    @pytest.mark.negative
    def test_duplicate_batch_refused(self, edit, saved):
        other = saved.journey.batches[1]
        edit_fields(edit, 0, batch_no=other)
        status, body = update(edit)
        assert status != 200, f"a Batch No already used by another line was accepted: {status}"

    @allure.story("An Expiry Date set on a line shows in the cart's Exp date column")
    def test_expiry_date_in_cart(self, edit):
        inv = edit.cart
        inv.edit_cart_row(inv.cart_row(0))
        inv.set_expiry_date(1, "Jan", 2031)
        inv.submit_cart_item()
        assert "2031" in inv.cart_rows()[0]["Exp date"], inv.cart_rows()[0]

    @allure.story("Large Box Qty is saved and billed exactly")
    def test_large_box_qty(self, edit, saved, record):
        specs = saved.journey.specs
        edit_line(edit, 0, 1000)
        total = bill(specs, [1000, specs[1].box_qty])
        _ok(update(edit))
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(final_price(total), abs=0.51)

    @allure.story("Several lines can be edited in one Edit Inventory session")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_edit_both_lines(self, edit, saved, record):
        specs = saved.journey.specs
        edit_line(edit, 0, 4)
        edit_line(edit, 1, 6)
        total = bill(specs, [4, 6])
        assert edit.cart.cart_total_price() == pytest.approx(total, abs=0.011)
        _ok(update(edit))
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(final_price(total), abs=0.51)


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditCartStructure:
    @allure.story("A new product added in Edit Inventory is saved with the record")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_add_product(self, edit, saved, record, flow):
        specs = saved.journey.specs
        edit.cart.add_line(P2, flow.next_batch("E"))
        assert edit.cart.total_items() == 3
        total = bill(specs) + P2.box_qty * P2.btp_vat_per_box
        assert edit.cart.cart_total_price() == pytest.approx(total, abs=0.011)
        _ok(update(edit))
        row = record_row(record, saved.inventory_id)
        assert "3" in row["qty"] and num(row["bill"]) == pytest.approx(final_price(total), abs=0.51), row

    @allure.story("A product already in the cart cannot be added again in Edit Inventory")
    @pytest.mark.negative
    def test_duplicate_product_refused(self, edit, saved, flow):
        specs = saved.journey.specs
        added, msgs = edit.cart.try_add_line(LineSpec("P0", box_qty=2, btp_vat_per_box=33.3, retail=60,
                                                      wholesale=50, min_qty=5, rack="A1"), flow.next_batch("E"))
        assert not added and edit.cart.total_items() == len(specs), msgs

    @allure.story("Deleting a line and updating removes it from the record")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_delete_line_saved(self, edit, saved, record):
        specs = saved.journey.specs
        edit.cart.delete_cart_row(edit.cart.cart_row(0))
        total = specs[1].box_qty * specs[1].btp_vat_per_box
        _ok(update(edit))
        row = record_row(record, saved.inventory_id)
        assert "1" in row["qty"] and num(row["bill"]) == pytest.approx(final_price(total), abs=0.51), row

    @allure.story("An edited cart with no lines cannot be taken to checkout")
    @pytest.mark.negative
    def test_empty_cart_cannot_checkout(self, edit):
        inv = edit.cart
        while inv.cart_row_count():
            inv.delete_cart_row(inv.cart_row(0))
        assert inv.total_items() == 0
        assert not inv.go_to_checkout_btn.is_enabled(), "Go to Inventory Checkout is enabled for an empty cart"


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditDiscount:
    @allure.story("A saved percentage discount is pre-loaded in the edit checkout")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_discount_preloaded(self, create, page):
        saved = create("two_plain", discount=(10, "%"))
        edit = reopen_edit(page, _record_page(page), saved.inventory_id)
        co = edit.go_to_checkout()
        total = bill(saved.journey.specs)
        s = co.summary()
        assert s["discount_amount"] == pytest.approx(total * 0.10, abs=0.011), \
            f"the saved 10% discount is not pre-loaded: {s}"

    @allure.story("Removing the discount in the edit checkout raises Final Price to Total Price and is saved")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_remove_discount(self, create, page):
        saved = create("two_plain", discount=(10, "%"))
        edit = reopen_edit(page, _record_page(page), saved.inventory_id)
        co = edit.go_to_checkout()
        co.set_discount(0, "%")
        total = bill(saved.journey.specs)
        assert co.summary()["final_price"] == pytest.approx(final_price(total), abs=0.011)
        _ok(edit.update_capturing_response(co))
        rec = _record_page(page)
        assert num(record_row(rec, saved.inventory_id)["bill"]) == pytest.approx(final_price(total), abs=0.51)

    @allure.story("A discount added in the edit checkout is saved: the Record's bill is the discounted Final Price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_add_discount_saved(self, edit, saved, record):
        total = bill(saved.journey.specs)
        co = edit.go_to_checkout()
        co.set_discount(10, "%")
        expected = final_price(total - total * 0.10)
        assert co.summary()["final_price"] == pytest.approx(expected, abs=0.011)
        co.set_paid_amount(expected)
        _ok(edit.update_capturing_response(co))
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(expected, abs=0.51)

    @allure.story("A flat discount (Tk) is applied in the edit checkout")
    def test_flat_discount(self, edit, saved):
        total = bill(saved.journey.specs)
        co = edit.go_to_checkout()
        co.set_discount(50, "Tk")
        s = co.summary()
        assert s["discount_amount"] == pytest.approx(50, abs=0.011), s
        assert s["final_price"] == pytest.approx(final_price(total - 50), abs=0.011), s


def _record_page(page):
    from pages.inventory_record_page import InventoryRecordPage
    return InventoryRecordPage(page)


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditPayment:
    @allure.story("Paying less than the new bill and taking Due & Buy leaves the shortfall as Due")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_due_and_buy(self, edit, saved, record):
        _ok(update(edit, paid=100, choice="Due & Buy"))
        row = record_row(record, saved.inventory_id)
        assert num(row["paid"]) == pytest.approx(100, abs=0.51) and row["status"] == "Due", row
        assert num(row["bill"]) == pytest.approx(saved.final, abs=0.51), row

    @allure.story("Paying nothing and taking Due & Buy leaves the whole bill Due")
    def test_pay_nothing(self, edit, saved, record):
        _ok(update(edit, paid=0, choice="Due & Buy"))
        row = record_row(record, saved.inventory_id)
        assert row["status"] == "Due" and num(row["paid"]) == pytest.approx(0, abs=0.51), row

    @allure.story("Paying less and taking Less & Buy waives the shortfall: the record is Paid")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_less_and_buy(self, edit, saved, record):
        _ok(update(edit, paid=saved.final - 40, choice="Less & Buy"))
        row = record_row(record, saved.inventory_id)
        assert row["status"] == "Paid", f"Less & Buy should settle the bill, got {row}"

    @allure.story("Paying more than the bill and taking Advance & Buy records an Advance")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_advance_and_buy(self, edit, saved, record):
        _ok(update(edit, paid=saved.final + 100, choice="Advance & Buy"))
        row = record_row(record, saved.inventory_id)
        assert row["status"] == "Advance" and num(row["paid"]) == pytest.approx(saved.final + 100, abs=0.51), row

    @allure.story("The payment method can be changed in the edit checkout and the Record shows it")
    @pytest.mark.parametrize("method", ["BANK", "CARD", "MFS"])
    def test_payment_method_changed(self, edit, saved, record, method):
        co = edit.go_to_checkout()
        co.set_payment_method(method)
        _ok(edit.update_capturing_response(co))
        row = record_row(record, saved.inventory_id)
        assert method in row["paid"].upper(), row

    @allure.story("The checkout payment dialog shows the right bill / paid / shortfall amounts on edit")
    def test_payment_dialog_amounts(self, edit, saved):
        co = edit.go_to_checkout()
        co.set_paid_amount(100)
        status, _ = edit.update_capturing_response(co, choice="Due & Buy")
        snap = co.last_payment_dialog or {}
        assert snap.get("kind") == "less", snap
        assert snap.get("bill") == pytest.approx(saved.final, abs=0.011), snap
        assert snap.get("paid") == pytest.approx(100, abs=0.011), snap
        assert snap.get("gap") == pytest.approx(saved.final - 100, abs=0.011), snap


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditStartingStates:
    @allure.story("Editing a Due inventory and paying the same amount keeps it Due for the same amount")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_edit_due_record(self, create, page):
        saved = create("two_plain", paid_ratio=0.5, choice="Due & Buy")
        rec = _record_page(page)
        edit = reopen_edit(page, rec, saved.inventory_id)
        _ok(update(edit, paid=saved.paid, choice="Due & Buy"))
        row = record_row(rec, saved.inventory_id)
        assert row["status"] == "Due" and num(row["paid"]) == pytest.approx(saved.paid, abs=0.51), row
        assert num(row["bill"]) == pytest.approx(saved.final, abs=0.51), row

    @allure.story("Editing an Advance inventory and paying the same amount keeps the Advance")
    def test_edit_advance_record(self, create, page):
        saved = create("two_plain", paid_delta=100, choice="Advance & Buy")
        rec = _record_page(page)
        edit = reopen_edit(page, rec, saved.inventory_id)
        _ok(update(edit, paid=saved.paid, choice="Advance & Buy"))
        row = record_row(rec, saved.inventory_id)
        assert row["status"] == "Advance" and num(row["paid"]) == pytest.approx(saved.paid, abs=0.51), row

    @allure.story("Editing a Borrowed inventory keeps its type")
    def test_edit_borrowed_record(self, create, page):
        saved = create("two_plain", inventory_type="Borrowed")
        rec = _record_page(page)
        edit = reopen_edit(page, rec, saved.inventory_id)
        co = edit.go_to_checkout()
        assert co.inventory_type() == "Borrowed", co.inventory_type()
        _ok(edit.update_capturing_response(co))
        assert record_row(rec, saved.inventory_id)["type"] == "Borrowed"

    @allure.story("Editing an inventory with Free Qty lines keeps the Free Qty and the discount base")
    def test_edit_free_qty_record(self, create, page):
        saved = create("two_one_free")
        rec = _record_page(page)
        edit = reopen_edit(page, rec, saved.inventory_id)
        free_cells = [r["Free"] for r in edit.cart.cart_rows()]
        assert any(c.strip() not in ("", "-") for c in free_cells), f"Free Qty not pre-loaded: {free_cells}"
        _ok(update(edit))
        assert record_row(rec, saved.inventory_id)["status"] == "Paid"


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditSupplierAndType:
    @allure.story("The inventory type is read-only in the edit checkout (the server refuses a type change)")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.negative
    def test_type_is_read_only(self, edit):
        co = edit.go_to_checkout()
        select = co.inventory_type_select
        disabled = "ant-select-disabled" in (select.root.get_attribute("class") or "")
        assert disabled, ("Inventory Type is editable in the edit checkout, but Update Inventory is refused with "
                          "'The inventory type cannot be changed by an edit.'")

    @allure.story("The supplier can be changed in the edit checkout and is saved")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_change_supplier(self, edit, saved, record):
        co = edit.go_to_checkout()
        options = co.supplier_select.open().options()
        others = [o for o in options if saved.supplier.lower() not in o.lower()]
        if not others:
            pytest.skip("only one supplier exists in this pharmacy")
        co.supplier_select.select(others[0].splitlines()[0], exact=False)
        _ok(edit.update_capturing_response(co))
        row = record_row(record, saved.inventory_id)
        assert saved.supplier.lower() not in row["supplier"].lower(), row

    @allure.story("An Invoice Number entered in the edit checkout is saved and pre-loaded next time")
    def test_invoice_number_persisted(self, edit, saved, record, page):
        co = edit.go_to_checkout()
        co.set_invoice_number("EDIT-INV-77")
        _ok(edit.update_capturing_response(co))
        again = reopen_edit(page, record, saved.inventory_id).go_to_checkout()
        assert again.invoice_number_input.input_value() == "EDIT-INV-77"


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditHistory:
    @allure.story("A record that was never edited has no changes in its Edit History")
    def test_history_empty_before_edit(self, saved, record):
        count, text = history_changes(record, saved.inventory_id)
        assert count == 0, text[-400:]

    @allure.story("An Update adds one 'Edit' entry, by the signed-in user, to the Edit History")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_history_after_update(self, edit, saved, record):
        _ok(update(edit, box_qty=5))
        count, text = history_changes(record, saved.inventory_id)
        assert count == 1, text[-400:]
        assert "Edit" in text and "by " in text, text[-400:]

    @allure.story("Two updates of the same record give two history entries and the second figures win")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_second_edit(self, edit, saved, record, page):
        specs = saved.journey.specs
        _ok(update(edit, box_qty=5))
        again = reopen_edit(page, record, saved.inventory_id)
        _ok(update(again, box_qty=7))
        count, text = history_changes(record, saved.inventory_id)
        assert count == 2, text[-400:]
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(
            final_price(bill(specs, [7, specs[1].box_qty])), abs=0.51)


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditNavigation:
    @allure.story("Leaving Edit Inventory without Update changes nothing")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_abandoned_edit_changes_nothing(self, edit, saved, record, page):
        edit_line(edit, 0, 9)
        row = record_row(record, saved.inventory_id)   # reload of the record list = leaving the edit screen
        assert num(row["bill"]) == pytest.approx(saved.final, abs=0.51), row
        count, _ = history_changes(record, saved.inventory_id)
        assert count == 0

    @allure.story("Edit Cart in the edit checkout returns to the edit cart with the changes intact")
    def test_edit_cart_from_edit_checkout(self, edit, saved):
        edit_line(edit, 0, 5)
        co = edit.go_to_checkout()
        inv = co.edit_cart()
        assert inv.total_items() == len(saved.journey.specs)
        assert num(inv.cart_rows()[0]["Box Qty"]) == 5

    @allure.story("A cancelled inventory cannot be edited: the row menu must not offer Edit Inventory")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_cancelled_record_not_editable(self, saved, record, page):
        record.choose_row_action(record.row_by_inventory_id(saved.inventory_id), "Cancel Inventory")
        page.get_by_role("button", name="Yes, cancel it").click()
        page.wait_for_timeout(3000)
        page.reload()
        record.wait_loaded()
        record.choose_filter("status", "Cancelled")
        items = record.open_row_menu(record.row_by_inventory_id(saved.inventory_id))
        assert "Edit Inventory" not in items, f"a Cancelled inventory still offers Edit Inventory: {items}"
