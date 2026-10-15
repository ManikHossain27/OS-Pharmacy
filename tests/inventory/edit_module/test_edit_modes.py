"""Edit Inventory for TP/VAT and Opening Stock records.

The Default-mode edit flow is covered in ``test_edit_inventory.py`` / ``test_edit_matrix.py``; these cases check that the
other two modes open their own edit screen, pre-load their saved lines, and that an update is saved in the mode's own
figures.  Expected amounts come from the edit checkout itself (the mode oracle already verifies the create flow's
checkout), so they check that the Record agrees with what the checkout showed - not the calculation again.
"""
from __future__ import annotations

import allure
import pytest

from pages.inventory_edit_page import EDIT_URL, InventoryEditPage
from pages.inventory_flow import OpeningStockFlow, TpVatFlow
from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.edit_module.conftest import create_inventory
from tests.inventory.edit_module.helpers import edit_line, num, record_row
from utils import opening_scenarios, tpvat_scenarios

MODES = {
    "TP/VAT": ("tpvat_inventory", TpVatFlow, tpvat_scenarios.CART_SHAPES),
    "Opening Stock": ("opening_inventory", OpeningStockFlow, opening_scenarios.CART_SHAPES),
}


@pytest.fixture(params=list(MODES), ids=lambda m: m.replace("/", "").replace(" ", "").lower())
def mode(request) -> str:
    return request.param


@pytest.fixture()
def mode_saved(request, mode, run_tag):
    """A fully paid two-line inventory created in ``mode``."""
    fixture, flow_cls, shapes = MODES[mode]
    inv = request.getfixturevalue(fixture)
    return create_inventory(flow_cls(inv, run_tag), "two_plain", shapes=shapes)


@pytest.fixture()
def mode_edit(page, mode_saved):
    record = InventoryRecordPage(page).open()
    record.reset_filters_btn.click()
    page.wait_for_timeout(1500)
    record.wait_loaded()
    return InventoryEditPage(page).open_for(record, mode_saved.inventory_id), record


@allure.epic("Inventory")
@allure.feature("Edit Inventory - modes")
class TestEditOtherModes:
    @allure.story("Edit Inventory opens the mode's own edit screen with the record id and mode badge")
    @pytest.mark.smoke
    def test_edit_page_shows_mode(self, mode, mode_saved, mode_edit, page):
        edit, _ = mode_edit
        assert EDIT_URL.search(page.url), page.url
        title = edit.heading_text()
        assert mode_saved.inventory_id in title and mode in title, title

    @allure.story("The cart is pre-loaded with the saved lines and the cart total")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cart_preloaded(self, mode_saved, mode_edit):
        edit, _ = mode_edit
        inv = edit.cart
        specs = mode_saved.journey.specs
        rows = inv.cart_rows()
        assert inv.total_items() == len(specs) == len(rows)
        for spec, row in zip(specs, rows):
            assert num(row["Box Qty"]) == spec.box_qty, row
        assert inv.cart_total_price() == pytest.approx(sum(num(r["Total Price"]) for r in rows), abs=0.011)

    @allure.story("A Box Qty change reprices the line at the same per-box price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_box_qty_change_reprices_line(self, mode_saved, mode_edit):
        edit, _ = mode_edit
        before = edit.cart.cart_rows()[0]
        old_qty = num(before["Box Qty"])
        per_box = num(before["Total Price"]) / old_qty
        edit_line(edit, 0, int(old_qty) + 2)
        after = edit.cart.cart_rows()[0]
        assert num(after["Box Qty"]) == old_qty + 2
        assert num(after["Total Price"]) == pytest.approx(per_box * (old_qty + 2), abs=0.02), (before, after)

    @allure.story("Update saves the edited bill: the Record's Bill and Paid equal the edit checkout's Final Price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_update_matches_checkout(self, mode, mode_saved, mode_edit):
        edit, record = mode_edit
        edit_line(edit, 0, int(num(edit.cart.cart_rows()[0]["Box Qty"])) + 2)
        co = edit.go_to_checkout()
        final = co.summary()["final_price"]
        assert final > mode_saved.final, "the larger Box Qty must raise the Final Price"
        status, body = edit.update_capturing_response(co)
        assert status == 200, f"update failed: {status} {body[:300]}"
        row = record_row(record, mode_saved.inventory_id)
        assert num(row["bill"]) == pytest.approx(final, abs=0.51), row
        assert num(row["paid"]) == pytest.approx(final, abs=0.51), row
        assert row["status"] == "Paid", row

    @allure.story("After an update the record's Details still show the mode it was created in")
    def test_mode_kept_after_update(self, mode, mode_saved, mode_edit):
        edit, record = mode_edit
        co = edit.go_to_checkout()
        status, body = edit.update_capturing_response(co)
        assert status == 200, f"update failed: {status} {body[:300]}"
        record.open()
        dlg = record.open_details_for(mode_saved.inventory_id).wait_loaded()
        assert dlg._value("Inventory Mode") == mode, dlg._value("Inventory Mode")
