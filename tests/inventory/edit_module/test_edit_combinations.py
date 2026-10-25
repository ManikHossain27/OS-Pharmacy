"""Edit Inventory - the combination matrix.

A record's starting state (paid / due / advance / borrowed / nothing paid / discounted) x the cart change (Box Qty up or
down, line deleted) x how the edit is paid (same amount, in full, half, nothing, over, less) is run in every mode.
Expectations are read from the edit checkout itself (its Final Price is the new bill), so one implementation serves
Default, TP/VAT and Opening Stock; a case passes when the Record shows what the checkout billed and what was typed,
the status follows the amounts, and (for Due / Advance outcomes) the supplier balance moves by the change in the gap.
Serial, headed: ``pytest tests/inventory/edit_module/test_edit_combinations.py --headed-run``.
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.edit_module.helpers import (
    apply_edit, edit_fields, edit_line, num, pay_and_update, record_row, reopen_edit)

STATES = {                         # starting state -> create_inventory kwargs
    "paid": {},
    "due": dict(paid_ratio=0.5, choice="Due & Buy"),
    "advance": dict(paid_delta=100, choice="Advance & Buy"),
    "borrowed": dict(inventory_type="Borrowed"),
    "nothing_paid": dict(paid_ratio=0, choice="Due & Buy"),
    "discounted": dict(discount=(10, "%")),
}


def _slug(mode: str) -> str:
    return mode.replace("/", "").replace(" ", "").lower()


def _grid(mode: str, states, edits, outcomes):
    return [pytest.param(mode, s, e, o, id=f"{_slug(mode)}-{s}-{e}-{o}")
            for s in states for e in edits for o in outcomes]


GRID = (
    _grid("Default", ["paid", "due", "advance"], ["up", "down"], ["keep", "full", "half", "zero", "over", "less"])
    + _grid("Default", ["paid", "due", "advance"], ["delete"], ["keep", "half", "over"])
    + _grid("Default", ["borrowed", "nothing_paid", "discounted"], ["up", "down"], ["keep", "full"])
    + sum((_grid(m, ["paid", "due", "advance"], ["up", "down"], ["keep", "half", "over"])
           + _grid(m, ["paid", "due", "advance"], ["delete"], ["keep"])
           + _grid(m, ["paid"], ["up"], ["zero", "less", "full"])
           + _grid(m, ["borrowed", "discounted"], ["up"], ["full"])
           for m in ("TP/VAT", "Opening Stock")), []))


def _ok(result) -> None:
    assert result.status == 200, f"Update Inventory failed: HTTP {result.status} {str(result.body)[:300]}"


@allure.epic("Inventory")
@allure.feature("Edit Inventory - combinations")
class TestStateEditPayment:
    @allure.story("Starting state x cart change x payment outcome: the Record, the status and the supplier balance follow")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("mode,state,edit_kind,outcome", GRID)
    def test_state_edit_outcome(self, create_in, flow, page, mode, state, edit_kind, outcome):
        saved = create_in(mode, "two_plain", **STATES[state])
        record = InventoryRecordPage(page)
        # the supplier balance is tracked for the outcomes that leave a Due / Advance (Less & Buy waives the gap)
        track = outcome != "less" and state != "borrowed"
        before = flow.supplier_balance(saved.supplier)[1] if track else None
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, edit_kind)
        result = pay_and_update(edit, outcome, saved.paid)
        _ok(result)
        row = record_row(record, saved.inventory_id)
        assert num(row["paid"]) == pytest.approx(result.paid, abs=0.51), (result, row)
        assert row["status"] == result.expected_status(outcome), (result, row)
        if outcome != "less":
            assert num(row["bill"]) == pytest.approx(result.final, abs=0.51), (result, row)
        if state == "borrowed":
            assert row["type"] == "Borrowed", row
        if track:
            after = flow.supplier_balance(saved.supplier)[1]
            expected = (result.final - result.paid) - (saved.final - saved.paid)
            assert after - before == pytest.approx(expected, abs=0.51), \
                f"supplier balance {before} -> {after}, expected a change of {expected} ({result})"


# ---- discount: what the record was saved with x what the edit does with it ----------------------------------------
DISCOUNTS = [   # (mode, saved discount, discount typed in the edit checkout - None keeps the saved one)
    ("Default", None, (10, "%")), ("Default", None, (30, "Tk")),
    ("Default", (10, "%"), None), ("Default", (10, "%"), (0, "%")), ("Default", (10, "%"), (20, "%")),
    ("Default", (10, "%"), (30, "Tk")),
    ("Default", (50, "Tk"), None), ("Default", (50, "Tk"), (0, "%")), ("Default", (50, "Tk"), (10, "%")),
    ("Default", (50, "Tk"), (20, "Tk")),
    ("TP/VAT", None, (10, "%")), ("TP/VAT", None, (30, "Tk")), ("TP/VAT", (10, "%"), (0, "%")), ("TP/VAT", (10, "%"), None),
    ("Opening Stock", None, (10, "%")), ("Opening Stock", None, (30, "Tk")), ("Opening Stock", (10, "%"), (0, "%")),
    ("Opening Stock", (10, "%"), None),
]


def _disc_id(v) -> str:
    return "none" if v is None else f"{v[0]}{'pct' if v[1] == '%' else 'tk'}"


@allure.epic("Inventory")
@allure.feature("Edit Inventory - combinations")
class TestDiscountMatrix:
    @allure.story("Saved discount x discount in the edit checkout (with a Box Qty increase): Final Price and the Record agree")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("mode,saved_discount,new_discount", DISCOUNTS,
                             ids=[f"{_slug(m)}-{_disc_id(a)}-to-{_disc_id(b)}" for m, a, b in DISCOUNTS])
    def test_discount_change(self, create_in, page, mode, saved_discount, new_discount):
        saved = create_in(mode, "two_plain", discount=saved_discount)
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, "up")
        co = edit.go_to_checkout()
        preloaded = co.summary()
        if new_discount is not None:
            co.set_discount(*new_discount)
        s = co.summary()
        if new_discount is None and saved_discount:
            assert preloaded["discount_amount"] > 0, f"the saved {saved_discount} discount is not pre-loaded: {preloaded}"
        value, unit = new_discount if new_discount is not None else (saved_discount or (0, "%"))
        expected_discount = s["total_price"] * value / 100 if unit == "%" else value
        if mode == "TP/VAT" and unit == "%" and value:      # spec 38: a TP/VAT percentage discount applies on TP only - VAT is never discounted
            assert 0 < s["discount_amount"] < expected_discount, (s, new_discount)
        else:
            assert s["discount_amount"] == pytest.approx(expected_discount, abs=0.02), (s, new_discount)
        assert s["final_price"] == pytest.approx(round(s["total_price"] - s["discount_amount"]), abs=0.51), s
        co.set_paid_amount(s["final_price"])
        status, body = edit.update_capturing_response(co)
        assert status == 200, f"update failed: {status} {body[:300]}"
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(s["final_price"], abs=0.51)
        again = reopen_edit(page, record, saved.inventory_id).go_to_checkout().summary()
        assert again["discount_amount"] == pytest.approx(s["discount_amount"], abs=0.02), \
            f"the saved discount did not reload: {again} vs {s}"


# ---- payment method x outcome --------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Edit Inventory - combinations")
class TestPaymentMethodMatrix:
    @allure.story("Payment method x outcome: the Record's Paid cell shows the method and the status follows the amount")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("method", ["CASH", "BANK", "CARD", "MFS"])
    @pytest.mark.parametrize("outcome", ["full", "half", "over"])
    def test_method_and_outcome(self, create_in, page, method, outcome):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        result = pay_and_update(edit, outcome, saved.paid, method=method)
        _ok(result)
        row = record_row(record, saved.inventory_id)
        assert method in row["paid"].upper(), row
        assert row["status"] == result.expected_status(outcome), (result, row)
        assert num(row["paid"]) == pytest.approx(result.paid, abs=0.51), row


# ---- several changes in one edit session ---------------------------------------------------------------------------
ALL_FIELDS = dict(retail_price=75, wholesale_price=55, min_qty=9, rack_no="Z9", free_qty=1)


@allure.epic("Inventory")
@allure.feature("Edit Inventory - combinations")
class TestCombinedChanges:
    @allure.story("Every line field changed at once is persisted")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_all_fields_at_once(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        edit_fields(edit, 0, **ALL_FIELDS)
        _ok(pay_and_update(edit, "full", saved.paid))
        again = reopen_edit(page, record, saved.inventory_id)
        again.cart.edit_cart_row(again.cart.cart_row(0))
        form = again.cart.form_snapshot()
        for key, value in ALL_FIELDS.items():
            assert form[key] == str(value) or num(form[key]) == pytest.approx(num(str(value)), abs=0.011), \
                f"{key}: saved {value!r}, reloaded {form[key]!r}"

    @allure.story("A Box Qty and a price change on the same line bill the new quantity at the new price")
    def test_box_qty_and_price_together(self, create_in, page):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        specs = saved.journey.specs
        edit_fields(edit, 0, box_qty=5, price_per_box=40)
        expected = round(5 * 40 + specs[1].box_qty * specs[1].btp_vat_per_box, 2)
        assert edit.cart.cart_total_price() == pytest.approx(expected, abs=0.011)
        _ok(pay_and_update(edit, "full", saved.paid))
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(round(expected), abs=0.51)

    @allure.story("Add a product, delete a line and edit the remaining line in one session")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_add_delete_and_edit_in_one_session(self, create_in, page, flow):
        from tests.inventory.edit_module.test_edit_matrix import P2
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        specs = saved.journey.specs
        edit.cart.add_line(P2, flow.next_batch("E"))
        edit.cart.delete_cart_row(edit.cart.cart_row(0))
        edit_fields(edit, 0, box_qty=4)               # the former second line
        expected = round(4 * specs[1].btp_vat_per_box + P2.box_qty * P2.btp_vat_per_box, 2)
        assert edit.cart.total_items() == 2 and edit.cart.cart_total_price() == pytest.approx(expected, abs=0.011)
        _ok(pay_and_update(edit, "full", saved.paid))
        row = record_row(record, saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(round(expected), abs=0.51) and "2" in row["qty"], row

    @allure.story("Box Qty up on both lines, a discount and a part payment: everything is saved together")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_kitchen_sink(self, create_in, page):
        saved = create_in("Default", "two_plain", paid_ratio=0.5, choice="Due & Buy")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, "up")
        edit_line(edit, 1, 6)
        result = pay_and_update(edit, "half", saved.paid, discount=(10, "%"))
        _ok(result)
        row = record_row(record, saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(result.final, abs=0.51) and row["status"] == "Due", (result, row)
        assert num(row["paid"]) == pytest.approx(result.paid, abs=0.51), row

    @allure.story("Free Qty added to a plain line of a discounted record is saved; the discount stays 10% of the total")
    def test_free_qty_with_discount(self, create_in, page):
        saved = create_in("Default", "two_plain", discount=(10, "%"))
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        edit_fields(edit, 0, free_qty=3)
        co = edit.go_to_checkout()
        s = co.summary()
        assert s["discount_amount"] > 0, s
        co.set_paid_amount(s["final_price"])
        status, body = edit.update_capturing_response(co)
        assert status == 200, f"update failed: {status} {body[:300]}"
        assert num(record_row(record, saved.inventory_id)["bill"]) == pytest.approx(s["final_price"], abs=0.51)

    @allure.story("A new Batch No and an Expiry Date on the same line are saved together")
    def test_batch_and_expiry_together(self, create_in, page, flow):
        saved = create_in("Default", "two_plain")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        batch = flow.next_batch("E")
        inv = edit.cart
        inv.edit_cart_row(inv.cart_row(0))
        inv.set_value("batch_no", batch)
        inv.set_expiry_date(1, "Jan", 2031)
        inv.submit_cart_item()
        _ok(pay_and_update(edit, "full", saved.paid))
        dlg = record.open().open_details_for(saved.inventory_id).wait_loaded()
        item = dlg.item_row_by_batch(batch)
        assert item and "2031" in " ".join(item.values()), (batch, dlg.item_rows())

    @allure.story("Raising Box Qty on both lines of a discounted, partly paid record keeps the Due consistent")
    def test_discounted_due_record_both_lines(self, create_in, page):
        saved = create_in("Default", "two_plain", discount=(10, "%"), paid_ratio=0.5, choice="Due & Buy")
        record = InventoryRecordPage(page)
        edit = reopen_edit(page, record, saved.inventory_id)
        apply_edit(edit, "up")
        edit_line(edit, 1, 6)
        result = pay_and_update(edit, "keep", saved.paid)
        _ok(result)
        row = record_row(record, saved.inventory_id)
        assert row["status"] == "Due" and num(row["bill"]) == pytest.approx(result.final, abs=0.51), (result, row)
