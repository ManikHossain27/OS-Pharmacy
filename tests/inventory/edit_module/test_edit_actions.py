"""Edit Inventory - what an edit does to the rest of the system, and what the other row actions see afterwards:
Return Inventory, Cancel Inventory, Pay Due, repeated edits, supplier change (two suppliers) and two people
editing the same record.  Pay Due itself needs an SMS OTP, so only what its dialog shows is checked.
Serial, headed: ``pytest tests/inventory/edit_module/test_edit_actions.py --headed-run``.
"""
from __future__ import annotations

import re

import allure
import pytest

from pages.inventory_edit_page import InventoryEditPage
from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage
from tests.inventory.edit_module.conftest import MODE_NAMES
from tests.inventory.edit_module.helpers import (
    apply_edit, edit_fields, edit_line, history_changes, num, pay_and_update, record_row, reopen_edit)


def _ok(result) -> None:
    assert result.status == 200, f"Update Inventory failed: HTTP {result.status} {str(result.body)[:300]}"


def _slug(mode: str) -> str:
    return mode.replace("/", "").replace(" ", "").lower()


# ---- Return Inventory ----------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - effects")
class TestReturnAfterEdit:
    @allure.story("Return Inventory of an edited record offers the edited quantities and the edited bill")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("edit_kind", ["up", "down"])
    def test_return_cart_follows_edit(self, create_in, page, edit_kind):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, edit_kind)
        result = pay_and_update(edit, "full", saved.paid)
        _ok(result)
        ret = InventoryReturnPage(page).open_for(record.open(), saved.inventory_id)
        rows = ret.cart_rows()
        box = int(saved.journey.specs[0].box_qty) + (3 if edit_kind == "up" else -1)
        assert len(rows) == 2 and rows[0]["qty"] == box * int(saved.journey.lines[0].qty_per_box), rows
        assert ret.cart_total() == pytest.approx(result.final, abs=0.51), (ret.cart_total(), result)

    @allure.story("A line deleted by an edit is not offered for return")
    def test_return_cart_after_delete(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, "delete")
        _ok(pay_and_update(edit, "full", saved.paid))
        rows = InventoryReturnPage(page).open_for(record.open(), saved.inventory_id).cart_rows()
        assert len(rows) == 1 and rows[0]["batch"] == saved.journey.batches[1], rows

    @allure.story("Returning from an Inventory Record leaves the Return Checkout supplier unselected (spec)")
    def test_return_supplier_not_preselected(self, create_in, page):
        saved = create_in("Default", "two_plain")
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        assert not ret.go_to_checkout().supplier_preselected(), "the Return Checkout pre-selected a supplier"

    @allure.story("A completed return marks the record Returned and the record can then no longer be edited")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_returned_record_not_editable(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, "up")
        _ok(pay_and_update(edit, "full", saved.paid))
        ret = InventoryReturnPage(page).open_for(record.open(), saved.inventory_id).go_to_checkout()
        if not ret.supplier_preselected():
            ret.select_supplier(saved.supplier)
        status, body = ret.complete()
        assert status in (200, 201), f"return failed: {status} {body[:300]}"
        row = record_row(record, saved.inventory_id)
        assert row["status"] == "Returned", row
        items = record.open_row_menu(record.row_by_inventory_id(saved.inventory_id))
        assert "Edit Inventory" not in items, f"a Returned inventory still offers Edit Inventory: {items}"


# ---- Cancel Inventory ----------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - effects")
class TestCancelAfterEdit:
    @allure.story("Cancelling an edited record reverses the edited amounts: the supplier balance returns to its pre-create value")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("mode", MODE_NAMES, ids=[_slug(m) for m in MODE_NAMES])
    def test_cancel_restores_supplier_balance(self, create_in, flow, page, mode):
        name, balance_before_create = flow.supplier_balance()
        saved = create_in(mode, "two_plain", paid_ratio=0.5, choice="Due & Buy")
        assert saved.supplier.lower() == name.lower()
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, "up")
        _ok(pay_and_update(edit, "keep", saved.paid))
        record.open().cancel_inventory(saved.inventory_id)
        assert flow.supplier_balance(name)[1] == pytest.approx(balance_before_create, abs=0.51), \
            "cancelling the edited inventory did not restore the supplier balance"
        record.open()
        record.choose_filter("status", "Cancelled")
        assert record.row_values(record.row_by_inventory_id(saved.inventory_id))["status"] == "Cancelled"

    @allure.story("A cancelled record's Edit History keeps the edit that was made before the cancellation")
    def test_history_kept_after_cancel(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        _ok(pay_and_update(edit, "full", saved.paid))
        record.open().cancel_inventory(saved.inventory_id)
        page.reload()
        record.wait_loaded()
        record.choose_filter("status", "Cancelled")
        record.choose_row_action(record.row_by_inventory_id(saved.inventory_id), "Inventory Edit History")
        page.get_by_text("Total Changes").wait_for(state="visible", timeout=15_000)
        drawer = page.locator("body").inner_text()
        drawer = drawer[drawer.index("Change History"):] if "Change History" in drawer else drawer
        assert re.search(r"Total Changes\s*[1-9]", drawer) and re.search(r"Edit\s+by", drawer), drawer[-500:]


# ---- Pay Due -------------------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - effects")
class TestPayDueAfterEdit:
    @allure.story("Pay Due offers the invoice's edited Due: the dialog settles this invoice first for the new shortfall")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("state,edit_kind,outcome", [
        ("paid", "up", "keep"), ("due", "up", "keep"), ("due", "down", "keep"), ("advance", "up", "keep"),
        ("due", "up", "full")], ids=lambda v: str(v))
    def test_pay_due_dialog_shows_edited_due(self, create_in, page, state, edit_kind, outcome):
        from tests.inventory.edit_module.test_edit_combinations import STATES
        saved = create_in("Default", "two_plain", **STATES[state])
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, edit_kind)
        result = pay_and_update(edit, outcome, saved.paid)
        _ok(result)
        due = round(result.final - result.paid, 2)
        text = record.open().pay_due_dialog_text(saved.inventory_id) if due > 0.5 else ""
        if due <= 0.5:
            items = record.open_row_menu(record.row_by_inventory_id(saved.inventory_id))
            assert "Pay Due" in items          # the action is listed; nothing is owed on this invoice
            return
        m = re.search(r"due Tk\s*([\d,\.]+)", text)
        assert m, f"the Pay Due dialog does not name this invoice's due: {text!r}"
        assert float(m.group(1).replace(",", "")) == pytest.approx(due, abs=0.51), (text, result)


# ---- repeated edits and history ------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - effects")
class TestRepeatedEdits:
    @allure.story("Three updates give three history entries and the last figures win")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_three_edits(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        last = None
        for box in (5, 3, 7):
            edit = reopen_edit(page, record, saved.inventory_id)
            edit_line(edit, 0, box)
            last = pay_and_update(edit, "full", saved.paid)
            _ok(last)
        count, text = history_changes(record, saved.inventory_id)
        assert count == 3, text[-500:]
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(last.final, abs=0.51)

    @allure.story("Raising a record and then restoring the original quantity gives back the original bill")
    def test_round_trip_restores_bill(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        box = int(saved.journey.specs[0].box_qty)
        for qty in (box + 3, box):
            edit = reopen_edit(page, record, saved.inventory_id)
            edit_line(edit, 0, qty)
            _ok(pay_and_update(edit, "full", saved.paid))
        row = record_row(record, saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(saved.final, abs=0.51) and row["status"] == "Paid", row

    @allure.story("A discount added in one edit is still there, and can be removed, in the next")
    def test_discount_across_two_edits(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        first = pay_and_update(reopen_edit(page, record, saved.inventory_id), "full", saved.paid, discount=(10, "%"))
        _ok(first)
        co = reopen_edit(page, record, saved.inventory_id).go_to_checkout()
        assert co.summary()["discount_amount"] > 0, "the discount saved by the first edit did not reload"
        second = pay_and_update(reopen_edit(page, record, saved.inventory_id), "full", first.paid, discount=(0, "%"))
        _ok(second)
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(saved.final, abs=0.51)

    @allure.story("A Due left by one edit can be settled by the next edit")
    def test_due_then_settled_by_next_edit(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        first = pay_and_update(reopen_edit(page, record, saved.inventory_id), "half", saved.paid)
        _ok(first)
        assert record_row(record, saved.inventory_id)["status"] == "Due"
        second = pay_and_update(reopen_edit(page, record, saved.inventory_id), "full", first.paid)
        _ok(second)
        row = record_row(record, saved.inventory_id)
        assert row["status"] == "Paid" and num(row["paid"]) == pytest.approx(second.final, abs=0.51), row

    @allure.story("Each history entry names the signed-in user and a date")
    def test_history_entries_have_user_and_date(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        for box in (4, 6):
            edit = reopen_edit(page, record, saved.inventory_id)
            edit_line(edit, 0, box)
            _ok(pay_and_update(edit, "full", saved.paid))
        count, text = history_changes(record, saved.inventory_id)
        assert count == 2 and len(re.findall(r"Edit\s+by\s+\S+", text)) == 2, text[-600:]


# ---- supplier (two suppliers) --------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - supplier")
class TestSupplierChange:
    def _balances(self, flow, *names):
        return [flow.supplier_balance(n)[1] for n in names]

    @allure.story("The edit checkout lists every supplier of the pharmacy")
    def test_supplier_options(self, saved, other_supplier, page):
        edit = reopen_edit(page, InventoryRecordPage(page), saved.inventory_id)
        options = [o.lower() for o in edit.go_to_checkout().supplier_select.open().options()]
        assert any(saved.supplier.lower() in o for o in options) and any(other_supplier.lower() in o for o in options), options

    @allure.story("Changing the supplier of a paid record saves the new supplier and leaves both balances alone")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_change_supplier_paid(self, create_in, flow, page, other_supplier):
        saved = create_in("Default", "two_plain")
        old_before, new_before = self._balances(flow, saved.supplier, other_supplier)
        record = InventoryRecordPage(page)
        _ok(pay_and_update(reopen_edit(page, record, saved.inventory_id), "keep", saved.paid, supplier=other_supplier))
        assert other_supplier.lower() in record_row(record, saved.inventory_id)["supplier"].lower()
        old_after, new_after = self._balances(flow, saved.supplier, other_supplier)
        assert (old_after, new_after) == (pytest.approx(old_before, abs=0.51), pytest.approx(new_before, abs=0.51))

    @allure.story("Changing the supplier of a Due record moves the Due from the old supplier to the new one")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_change_supplier_due_moves_balance(self, create_in, flow, page, other_supplier):
        saved = create_in("Default", "two_plain", paid_ratio=0.5, choice="Due & Buy")
        due = saved.final - saved.paid
        old_before, new_before = self._balances(flow, saved.supplier, other_supplier)
        record = InventoryRecordPage(page)
        _ok(pay_and_update(reopen_edit(page, record, saved.inventory_id), "keep", saved.paid, supplier=other_supplier))
        old_after, new_after = self._balances(flow, saved.supplier, other_supplier)
        assert old_after - old_before == pytest.approx(-due, abs=0.51), (old_before, old_after, due)
        assert new_after - new_before == pytest.approx(due, abs=0.51), (new_before, new_after, due)

    @allure.story("Changing the supplier of an Advance record moves the Advance to the new supplier")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_change_supplier_advance_moves_balance(self, create_in, flow, page, other_supplier):
        saved = create_in("Default", "two_plain", paid_delta=100, choice="Advance & Buy")
        advance = saved.paid - saved.final
        old_before, new_before = self._balances(flow, saved.supplier, other_supplier)
        record = InventoryRecordPage(page)
        _ok(pay_and_update(reopen_edit(page, record, saved.inventory_id), "keep", saved.paid, supplier=other_supplier))
        old_after, new_after = self._balances(flow, saved.supplier, other_supplier)
        assert old_after - old_before == pytest.approx(advance, abs=0.51), (old_before, old_after, advance)
        assert new_after - new_before == pytest.approx(-advance, abs=0.51), (new_before, new_after, advance)

    @allure.story("Changing the supplier and raising Box Qty in one edit: the new supplier carries the whole new Due")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_change_supplier_with_box_qty(self, create_in, flow, page, other_supplier):
        saved = create_in("Default", "two_plain")
        old_before, new_before = self._balances(flow, saved.supplier, other_supplier)
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, "up")
        result = pay_and_update(edit, "keep", saved.paid, supplier=other_supplier)
        _ok(result)
        old_after, new_after = self._balances(flow, saved.supplier, other_supplier)
        assert old_after == pytest.approx(old_before, abs=0.51), (old_before, old_after)
        assert new_after - new_before == pytest.approx(result.final - result.paid, abs=0.51), (new_before, new_after, result)

    @allure.story("Changing the supplier and changing it back leaves both balances where they started")
    def test_change_supplier_and_back(self, create_in, flow, page, other_supplier):
        saved = create_in("Default", "two_plain", paid_ratio=0.5, choice="Due & Buy")
        old_before, new_before = self._balances(flow, saved.supplier, other_supplier)
        record = InventoryRecordPage(page)
        _ok(pay_and_update(reopen_edit(page, record, saved.inventory_id), "keep", saved.paid, supplier=other_supplier))
        _ok(pay_and_update(reopen_edit(page, record, saved.inventory_id), "keep", saved.paid, supplier=saved.supplier))
        old_after, new_after = self._balances(flow, saved.supplier, other_supplier)
        assert (old_after, new_after) == (pytest.approx(old_before, abs=0.51), pytest.approx(new_before, abs=0.51))
        assert saved.supplier.lower() in record_row(record, saved.inventory_id)["supplier"].lower()

    @allure.story("The saved supplier is pre-selected when the record is edited again")
    def test_supplier_preselected_after_change(self, create_in, page, other_supplier):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        _ok(pay_and_update(reopen_edit(page, record, saved.inventory_id), "keep", saved.paid, supplier=other_supplier))
        co = reopen_edit(page, record, saved.inventory_id).go_to_checkout()
        assert other_supplier.lower() in page.locator("body").inner_text().lower() and co.supplier_selected()

    @allure.story("TP/VAT and Opening Stock records can change supplier too")
    @pytest.mark.parametrize("mode", ["TP/VAT", "Opening Stock"], ids=["tpvat", "openingstock"])
    def test_change_supplier_other_modes(self, create_in, page, other_supplier, mode):
        saved = create_in(mode, "two_plain")
        record = InventoryRecordPage(page)
        _ok(pay_and_update(reopen_edit(page, record, saved.inventory_id), "keep", saved.paid, supplier=other_supplier))
        assert other_supplier.lower() in record_row(record, saved.inventory_id)["supplier"].lower()


# ---- two people editing the same record ---------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - concurrency")
class TestConcurrentEdit:
    @allure.story("Two edits of the same record: the Record ends up with the figures of the update that was accepted last")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_two_tabs_editing_the_same_record(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record_a = InventoryRecordPage(page)
        edit_a = reopen_edit(page, record_a, saved.inventory_id)
        other = page.context.new_page()
        try:
            record_b = InventoryRecordPage(other).open()
            edit_b = InventoryEditPage(other).open_for(record_b, saved.inventory_id)
            edit_line(edit_b, 0, 7)
            result_b = pay_and_update(edit_b, "full", saved.paid)
            _ok(result_b)
            edit_line(edit_a, 0, 4)                     # tab A still holds the pre-edit record
            result_a = pay_and_update(edit_a, "full", saved.paid)
        finally:
            other.close()
        row = record_row(record_a, saved.inventory_id)
        accepted = result_a.final if result_a.status == 200 else result_b.final
        assert num(row["bill"]) == pytest.approx(accepted, abs=0.51), \
            f"A: {result_a.status} {result_a.final}, B: {result_b.final}; the Record shows {row}"
        count, _ = history_changes(record_a, saved.inventory_id)
        assert count == (2 if result_a.status == 200 else 1), count
