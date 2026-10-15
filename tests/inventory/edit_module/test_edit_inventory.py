"""Edit Inventory (Inventory Record -> row menu -> Edit Inventory -> cart -> Edit Inventory Checkout -> Update).

Every test creates its own two-line, fully paid Default inventory (``saved``) and edits that one.
The spec has no dedicated section for the edit flow; the expectations below are the ones the create flow already
defines (spec 27-44.1) applied to an existing record, so a figure that differs is reported as a finding.
Serial, headed: ``pytest tests/inventory/edit_module --headed-run``.
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_edit_page import EDIT_CHECKOUT_URL, EDIT_URL, InventoryEditPage
from tests.inventory.edit_module.helpers import bill, edit_line, final_price, num, record_row, update

MENU = ["View Details", "Edit Inventory", "Inventory Edit History", "Pay Due", "Return Inventory", "Cancel Inventory"]


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditEntry:
    @allure.story("The row menu offers the six record actions, Edit Inventory among them")
    def test_row_menu_items(self, record, saved):
        assert record.open_row_menu(record.row_by_inventory_id(saved.inventory_id)) == MENU

    @allure.story("Edit Inventory opens /inventory/edit/<id> with the record id and mode in the title")
    @pytest.mark.smoke
    def test_opens_edit_page(self, edit, saved, page):
        assert EDIT_URL.search(page.url), page.url
        title = edit.heading_text()
        assert saved.inventory_id in title and "Default" in title, title

    @allure.story("The cart is pre-loaded with every saved line: Box Qty, BTP+VAT, Total Price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cart_preloaded_with_saved_lines(self, edit, saved):
        inv = edit.cart
        specs = saved.journey.specs
        rows = inv.cart_rows()
        assert inv.total_items() == len(specs) and len(rows) == len(specs)
        for spec, row in zip(specs, rows):
            assert num(row["Box Qty"]) == spec.box_qty, row
            assert num(row["BTP+VAT"]) == pytest.approx(spec.btp_vat_per_box, abs=0.011), row
            assert num(row["Total Price"]) == pytest.approx(spec.box_qty * spec.btp_vat_per_box, abs=0.011), row
        assert inv.cart_total_price() == pytest.approx(bill(specs), abs=0.011)

    @allure.story("Editing a line pre-loads every field the line was saved with")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_line_form_preloaded(self, edit, saved):
        inv = edit.cart
        inv.edit_cart_row(inv.cart_row(0))
        assert inv.is_edit_mode()
        spec, batch = saved.journey.specs[0], saved.journey.batches[0]
        form = inv.form_snapshot()
        expected = {"box_qty": spec.box_qty, "price_per_box": spec.btp_vat_per_box, "retail_price": spec.retail,
                    "wholesale_price": spec.wholesale, "min_qty": spec.min_qty}
        for key, want in expected.items():
            assert num(form[key]) == pytest.approx(want, abs=0.011), f"{key}: {form[key]!r} != {want}"
        assert form["rack_no"] == spec.rack and form["batch_no"] == batch, form


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditCart:
    @allure.story("Changing Box Qty updates that line's Total Price and the cart total")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_box_qty_change_recalculates_cart(self, edit, saved):
        specs = saved.journey.specs
        edit_line(edit, 0, 5)
        rows = edit.cart.cart_rows()
        assert num(rows[0]["Box Qty"]) == 5
        assert num(rows[0]["Total Price"]) == pytest.approx(5 * specs[0].btp_vat_per_box, abs=0.011)
        assert edit.cart.cart_total_price() == pytest.approx(bill(specs, [5, specs[1].box_qty]), abs=0.011)

    @allure.story("Deleting a line removes it from the cart and the total")
    def test_delete_line(self, edit, saved):
        specs = saved.journey.specs
        edit.cart.delete_cart_row(edit.cart.cart_row(0))
        assert edit.cart.total_items() == len(specs) - 1
        assert edit.cart.cart_total_price() == pytest.approx(specs[1].box_qty * specs[1].btp_vat_per_box, abs=0.011)

    @allure.story("A line cannot be changed to Box Qty 0")
    @pytest.mark.negative
    def test_box_qty_zero_rejected(self, edit):
        inv = edit.cart
        inv.edit_cart_row(inv.cart_row(0))
        inv.type_value("box_qty", "0")
        inv.click(inv.submit_button(), description="Save Changes")
        edit.page.wait_for_timeout(1500)
        assert num(inv.cart_rows()[0]["Box Qty"]) != 0, "BUG-INV-030: Box Qty 0 was accepted when editing a line"


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestEditCheckout:
    @allure.story("Edit Inventory Checkout opens at /inventory/edit/checkout/<id> with the saved supplier and type")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_checkout_keeps_supplier_and_type(self, edit, saved, page):
        co = edit.go_to_checkout()
        assert EDIT_CHECKOUT_URL.search(page.url), page.url
        assert co.inventory_type() == "Purchase"
        assert saved.supplier.lower() in page.locator("body").inner_text().lower()
        assert edit.update_btn.is_visible()

    @allure.story("Checkout totals follow the edited cart: Total Price, Round Off, Final Price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_checkout_totals_after_box_qty_change(self, edit, saved):
        specs = saved.journey.specs
        edit_line(edit, 0, 5)
        total = bill(specs, [5, specs[1].box_qty])
        s = edit.go_to_checkout().summary()
        assert s["total_price"] == pytest.approx(total, abs=0.011)
        assert s["final_price"] == pytest.approx(final_price(total), abs=0.011), s
        assert s["round_off"] == pytest.approx(final_price(total) - total, abs=0.011), s

    @allure.story("A discount set in the edit checkout is applied to the cart total")
    def test_discount_in_edit_checkout(self, edit, saved):
        total = bill(saved.journey.specs)
        co = edit.go_to_checkout()
        co.set_discount(10, "%")
        s = co.summary()
        assert s["discount_amount"] == pytest.approx(total * 0.10, abs=0.011), s
        assert s["final_price"] == pytest.approx(final_price(total - total * 0.10), abs=0.011), s

    @allure.story("Total Paid is pre-filled with the amount originally paid, so the increase shows as Due")
    @pytest.mark.negative
    def test_total_paid_prefilled_with_original_payment(self, edit, saved):
        edit_line(edit, 0, 5)
        shown = num(edit.go_to_checkout().total_paid())
        assert shown == pytest.approx(saved.paid, abs=0.51),             f"BUG-INV-038: Total Paid shows {shown}, the originally paid amount was {saved.paid}"


@allure.epic("Inventory")
@allure.feature("Edit Inventory")
class TestUpdate:
    @allure.story("Update with no change succeeds and leaves the Bill and Paid amounts as they were")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_update_without_change(self, edit, saved, record):
        final = final_price(bill(saved.journey.specs))
        status, body = update(edit)
        assert status == 200, f"update failed: {status} {body[:300]}"
        row = record_row(record, saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(final, abs=0.51), row
        assert num(row["paid"]) == pytest.approx(final, abs=0.51), row
        assert row["status"] == "Paid", row

    @allure.story("Increasing Box Qty and paying the new Final Price updates the Record's Bill / Paid amounts")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_update_box_qty_paid_in_full(self, edit, saved, record):
        specs = saved.journey.specs
        new_final = final_price(bill(specs, [5, specs[1].box_qty]))
        status, body = update(edit, box_qty=5)
        assert status == 200, f"update failed: {status} {body[:300]}"
        row = record_row(record, saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(new_final, abs=0.51), row
        assert num(row["paid"]) == pytest.approx(new_final, abs=0.51), row
        assert row["status"] == "Paid", row

    @allure.story("The updated line shows in Inventory Details with the new Box Qty and Total Price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_details_show_updated_line(self, edit, saved, record):
        specs = saved.journey.specs
        status, body = update(edit, box_qty=5)
        assert status == 200, f"update failed: {status} {body[:300]}"
        record.page.reload()
        record.wait_loaded()
        dlg = record.open_details_for(saved.inventory_id).wait_loaded()
        item = dlg.item_row_by_batch(saved.journey.batches[0])
        assert item, f"batch {saved.journey.batches[0]} missing from details: {dlg.item_rows()}"
        assert item["Qty"].split()[0] == "5", item
        assert num(item["Price"]) == pytest.approx(5 * specs[0].btp_vat_per_box, abs=0.51), item

    @allure.story("Paying only the original amount after an increase leaves the extra as Due on the record")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_update_with_due(self, edit, saved, record):
        specs = saved.journey.specs
        old_final = final_price(bill(specs))
        new_final = final_price(bill(specs, [5, specs[1].box_qty]))
        status, body = update(edit, box_qty=5, paid=old_final, choice="Due & Buy")
        assert status == 200, f"update failed: {status} {body[:300]}"
        row = record_row(record, saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(new_final, abs=0.51), row
        assert num(row["paid"]) == pytest.approx(old_final, abs=0.51), row
        assert row["status"] == "Due", row

    @allure.story("The supplier balance moves by the change in the bill when the paid amount stays the same")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_supplier_balance_follows_edit(self, saved, record, flow, page):
        specs = saved.journey.specs
        old_final = final_price(bill(specs))
        new_final = final_price(bill(specs, [5, specs[1].box_qty]))
        _, before = flow.supplier_balance(saved.supplier)
        edit = InventoryEditPage(page).open_for(record.open(), saved.inventory_id)
        status, body = update(edit, box_qty=5, paid=old_final, choice="Due & Buy")
        assert status == 200, f"update failed: {status} {body[:300]}"
        _, after = flow.supplier_balance(saved.supplier)
        assert after - before == pytest.approx(new_final - old_final, abs=0.51),             f"supplier balance {before} -> {after}, expected +{new_final - old_final}"

    @allure.story("A refused update is reported to the user")
    @pytest.mark.negative
    def test_refused_update_is_reported(self, edit, page):
        """The CASH account is overdrawn on staging, so an update paid in CASH is refused with HTTP 400."""
        co = edit.go_to_checkout()
        co.set_payment_method("CASH")
        status, body = edit.update_capturing_response(co)
        if status == 200:
            pytest.skip("CASH accepted the payment on this environment - nothing to report")
        assert status == 400, (status, body[:200])
        page.wait_for_timeout(1000)
        assert "insufficient balance" in page.locator("body").inner_text().lower(), "the refusal was not shown to the user"
