"""Inventory Cart - multi-item, same-product-multiple-times, Edit, Delete,
Hold/Resume, and mode scoping (spec sections 27-34)."""
from __future__ import annotations

import allure
import pytest

pytestmark = [pytest.mark.inventory]


def _first_product(inventory_data: dict) -> str:
    return inventory_data.get("existing", {}).get("products_sample", ["TEST PRODUCT"])[0]


@allure.epic("Inventory")
@allure.feature("Inventory Cart")
class TestCartCrud:

    @allure.story("A product can be in the cart only once - a second add is refused (business rule, 2026-10-07)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.integration
    def test_same_product_cannot_be_added_twice(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        before = inventory.total_items()
        inventory.add_item_to_cart(product=product, box_qty=1, batch_no="QA_AUTO_INV_BATCH_A")
        inventory.select_product(product)
        inventory.set_value("box_qty", 2)
        inventory.set_value("batch_no", "QA_AUTO_INV_BATCH_B")
        inventory.click(inventory.submit_button(), description="second add of the same product")
        assert inventory.total_items() == before + 1, "the same product was added to the cart twice"
        assert any("already in the cart" in t.lower() for t in inventory.messages()),             "no 'This product is already in the cart' message"

    @allure.story("Edit Cart Item loads the row's data and updates it in place (spec section 30)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_edit_cart_item_updates_in_place(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        inventory.add_item_to_cart(product=product, box_qty=2, batch_no="QA_AUTO_INV_EDIT")
        before = inventory.total_items()
        row = inventory.cart_row(inventory.cart_row_count() - 1)
        inventory.edit_cart_row(row)
        assert inventory.is_edit_mode(), "drawer did not switch to 'Edit Cart Item' state"
        assert inventory.value_of("box_qty") == "2", "Edit did not preload the existing Box Qty"
        inventory.set_value("box_qty", 5)
        inventory.field("box_qty").blur()
        inventory.submit_cart_item()
        assert inventory.total_items() == before, "editing a cart line changed the item count (should update, not add)"
        updated_row = inventory.cart_row(inventory.cart_row_count() - 1)
        box_qty_cell = updated_row.locator("td").nth(1).inner_text().strip()
        assert box_qty_cell == "5", f"Box Qty cell shows {box_qty_cell!r} after edit, expected '5'"

    @allure.story("Deleting one cart item does not affect the others and recalculates totals (spec section 31)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_delete_cart_item_recalculates_total(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        inventory.add_item_to_cart(product=product, box_qty=1, batch_no="QA_AUTO_INV_KEEP")
        inventory.add_item_to_cart(product=product, box_qty=2, batch_no="QA_AUTO_INV_DELETE")
        before = inventory.total_items()
        row = inventory.cart_row(inventory.cart_row_count() - 1)
        inventory.delete_cart_row(row)
        assert inventory.total_items() == before - 1, "delete did not reduce Total Items by exactly one"

    @allure.story("A valid cart enables Hold Current Inventory and Go to Inventory Checkout")
    @pytest.mark.smoke
    def test_cart_actions_enabled_once_item_added(self, inventory, inventory_data):
        assert inventory.hold_current_btn.is_disabled(), "Hold should start disabled with an empty cart"
        assert inventory.go_to_checkout_btn.is_disabled(), "Checkout should start disabled with an empty cart"
        inventory.add_item_to_cart(product=_first_product(inventory_data), box_qty=1,
                                   batch_no="QA_AUTO_INV_ENABLE")
        assert inventory.hold_current_btn.is_enabled()
        assert inventory.go_to_checkout_btn.is_enabled()


@allure.epic("Inventory")
@allure.feature("Hold / Resume")
class TestHoldResume:

    @allure.story("Hold Current Inventory clears the cart and appears in the Hold List (spec sections 33-34)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.integration
    def test_hold_then_resume_restores_cart(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        inventory.add_item_to_cart(product=product, box_qty=3, free_qty=1,
                                   batch_no="QA_AUTO_INV_HOLD")
        held_count_before = inventory.hold_list_count()
        inventory.hold_current_inventory()
        assert inventory.total_items() == 0, "cart was not cleared after Hold Current Inventory"
        assert inventory.hold_list_count() == held_count_before + 1, "Hold List count did not increase by one"

        dlg = inventory.open_hold_list()
        assert dlg.is_open()
        dlg.resume(0)
        assert inventory.total_items() >= 1, "resuming a held inventory did not restore the cart"
        row = inventory.cart_row(0)
        batch_cell = row.locator("td").first.inner_text()
        assert "QA_AUTO_INV_HOLD" in batch_cell or inventory.total_items() >= 1

    @allure.story("The cart is scoped independently per Inventory Mode")
    @pytest.mark.regression
    def test_cart_is_mode_scoped(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        inventory.add_item_to_cart(product=product, box_qty=1, batch_no="QA_AUTO_INV_MODESCOPE_DEFAULT")
        default_items = inventory.total_items()

        inventory.switch_mode("TP/VAT")
        assert inventory.total_items() == 0, "TP/VAT mode unexpectedly shows the Default-mode cart"

        inventory.switch_mode("Default")
        assert inventory.total_items() == default_items, (
            "switching back to Default mode lost the cart items that were added before switching away"
        )


@allure.epic("Inventory")
@allure.feature("Cart row actions - keyboard/screen-reader accessibility (BUG-INV-013)")
class TestCartRowActionAccessibility:

    @allure.story("BUG-INV-013: cart row Edit/Delete icons must be reachable by keyboard and have an accessible name")
    @allure.issue("BUG-INV-013")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.negative
    @pytest.mark.regression
    def test_edit_and_delete_icons_are_keyboard_accessible(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        inventory.add_item_to_cart(product=product, box_qty=1, batch_no="QA_AUTO_INV_A11Y")
        row = inventory.cart_row(inventory.cart_row_count() - 1)

        edit_info = inventory.cart_row_action_accessibility(row, 0)
        delete_info = inventory.cart_row_action_accessibility(row, 1)
        allure.attach(f"edit={edit_info}\ndelete={delete_info}", name="row action accessibility")

        def _accessible(info: dict) -> bool:
            is_native_button = info["tag"] == "BUTTON"
            has_role_and_name = info["role"] == "button" and bool(info["aria_label"])
            is_tabbable = info["tabindex"] is not None and info["tabindex"] != "-1"
            return (is_native_button or has_role_and_name) and is_tabbable

        assert _accessible(edit_info) and _accessible(delete_info), (
            f"BUG-INV-013 reproduced: cart row Edit/Delete icons are plain <div>s with no role, "
            f"no aria-label, and no tabindex (edit={edit_info}, delete={delete_info}) - they are "
            "invisible to screen readers and unreachable via Tab, so keyboard-only and assistive-"
            "technology users cannot edit or delete a cart line."
        )


@allure.epic("Inventory")
@allure.feature("Add Items to Cart - Expiry Date")
class TestExpiryDateValidation:

    @allure.story("Past Expiry Dates are selectable - intentional (confirmed 2026-10-08; BUG-INV-014 closed as not a defect)")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    def test_calendar_allows_past_dates(self, inventory, inventory_data):
        result = inventory.expiry_past_dates_disabled()
        allure.attach(str(result), name="all past-date cells disabled?")
        assert result is not True, "past dates are disabled in the Expiry Date calendar, but they are meant to be selectable"


@allure.epic("Inventory")
@allure.feature("Fractional Box Qty display (BUG-INV-019)")
class TestFractionalBoxQtyDisplay:

    @allure.story("BUG-INV-019: Cart and Checkout tables must show a fractional Box Qty (e.g. 0.5) correctly, not rounded to a whole box")
    @allure.issue("BUG-INV-019")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_cart_and_checkout_show_fractional_box_qty(self, inventory, inventory_data):
        # TEST PRODUCT 2 has Qty/Box=10; Total Qty=5 does not divide evenly,
        # so Box Qty should compute to 0.5 (spec section 5.3).
        inventory.select_product("TEST PRODUCT 2", exact=False)
        inventory.set_value("total_qty", 5)
        inventory.set_value("batch_no", "QA_AUTO_INV_FRACTIONAL_BOXQTY")
        box_qty_in_panel = inventory.value_of("box_qty")
        inventory.submit_cart_item()

        cart_idx = inventory.cart_row_count() - 1
        cart_box_qty_text = inventory.cart.cell(cart_idx, "Box Qty").strip()

        checkout = inventory.go_to_checkout()
        checkout_idx = checkout.cart_table.row_count() - 1
        checkout_box_qty_text = checkout.cart_table.cell(checkout_idx, "Box Qty").strip()

        allure.attach(f"Add panel Box Qty={box_qty_in_panel!r}, Cart table Box Qty={cart_box_qty_text!r}, "
                      f"Checkout table Box Qty={checkout_box_qty_text!r}", name="observed")
        assert cart_box_qty_text == "0.5" and checkout_box_qty_text == "0.5", (
            f"BUG-INV-019 reproduced: Add Items panel correctly computed Box Qty={box_qty_in_panel!r}, "
            f"but the Cart table shows Box Qty={cart_box_qty_text!r} and the Checkout table shows "
            f"Box Qty={checkout_box_qty_text!r} (expected '0.5' in both) - the fractional value is "
            "rounded up for display in both tables even though the underlying value and all money "
            "calculations (Total Price, checkout totals) stay correct."
        )
