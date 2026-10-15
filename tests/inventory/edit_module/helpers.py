"""Helpers shared by the Edit Inventory test modules."""
from __future__ import annotations

import re

from tests.inventory.edit_module.conftest import PAYMENT_METHOD
from utils.inventory_calc import excel_round


def num(text: str) -> float:
    m = re.search(r"-?[\d,]+(?:\.\d+)?", text or "")
    return float(m.group().replace(",", "")) if m else float("nan")


def bill(specs, box_qtys=None) -> float:
    """Total price of the lines (Box Qty x BTP+VAT/Box), with an optional Box Qty override per line."""
    return round(sum((box_qtys[i] if box_qtys else s.box_qty) * s.btp_vat_per_box for i, s in enumerate(specs)), 2)


def final_price(total: float) -> float:
    return float(excel_round(total))


def edit_fields(edit, index: int = 0, **fields) -> None:
    """Open cart line ``index`` for editing, set the given form fields (``box_qty=5, rack_no="Z9"``) and save the line."""
    inv = edit.cart
    inv.edit_cart_row(inv.cart_row(index))
    for key, value in fields.items():
        inv.set_value(key, value)
    inv.submit_cart_item()


def edit_line(edit, index: int, box_qty: int) -> None:
    edit_fields(edit, index, box_qty=box_qty)


def reopen_edit(page, record, inventory_id: str):
    """Leave the current screen and open Edit Inventory for ``inventory_id`` again (fresh load from the server)."""
    from pages.inventory_edit_page import InventoryEditPage
    return InventoryEditPage(page).open_for(record.open(), inventory_id)


def history_changes(record, inventory_id: str) -> tuple[int, str]:
    """(Total Changes, drawer text) of the record's Inventory Edit History."""
    record.open()
    record.row_by_inventory_id(inventory_id).wait_for(state="visible", timeout=30_000)
    record.choose_row_action(record.row_by_inventory_id(inventory_id), "Inventory Edit History")
    record.page.get_by_text("Total Changes").wait_for(state="visible", timeout=15_000)
    text = record.page.locator("body").inner_text()
    text = text[text.index("Change History"):] if "Change History" in text else text
    m = re.search(r"Total Changes\s*(\d+)", text)
    return (int(m.group(1)) if m else -1), text


def record_row(record, inventory_id: str) -> dict:
    """The record's list row, read from a fresh load of Inventory Record."""
    record.open()
    row = record.row_by_inventory_id(inventory_id)
    row.wait_for(state="visible", timeout=30_000)
    return record.row_values(row)


def update(edit, *, box_qty: int | None = None, paid: float | None = None, choice: str | None = None):
    """Optionally change line 0's Box Qty and the paid amount, then press Update Inventory."""
    if box_qty is not None:
        edit_line(edit, 0, box_qty)
    co = edit.go_to_checkout()
    if paid is not None:
        co.set_paid_amount(paid)
        if paid > 0:
            co.set_payment_method(PAYMENT_METHOD)
    return edit.update_capturing_response(co, choice)
