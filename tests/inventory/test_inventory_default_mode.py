"""Inventory - Default mode: quantity + BTP/VAT calculation dependencies
(spec sections 5, 8; Calculation Dependency Matrix section 45)."""
from __future__ import annotations

import allure
import pytest

pytestmark = [pytest.mark.inventory]


def _first_product(inventory_data: dict) -> str:
    return inventory_data.get("existing", {}).get("products_sample", ["TEST PRODUCT"])[0]


@allure.epic("Inventory")
@allure.feature("Default mode - Add Items to Cart panel")
class TestDefaultModeCalculations:

    @allure.story("Panel opens by default with all expected fields")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_panel_open_with_fields(self, inventory):
        assert inventory.current_mode() == "Default"
        assert inventory.panel_open()
        for key in ("product", "box_qty", "qty_per_box", "total_qty", "free_qty",
                    "total_price", "price_per_box", "retail_price", "wholesale_price",
                    "min_qty", "rack_no", "batch_no", "expiry_date", "barcode_value"):
            assert inventory.field(key).count() == 1, f"field {key!r} missing in Default mode"

    @allure.story("Selecting a product loads Qty/Box, Retail and Wholesale Price defaults")
    @pytest.mark.smoke
    def test_product_selection_loads_defaults(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        inventory.select_product(product)
        assert inventory.value_of("qty_per_box") not in ("", "0"), "Qty/Box was not preloaded"
        assert inventory.value_of("retail_price") != "", "Retail Price/Box was not preloaded"

    @allure.story("Total Qty = Box Qty x Qty/Box (spec 5.3)")
    @pytest.mark.regression
    def test_box_qty_times_qty_per_box_equals_total_qty(self, inventory, inventory_data):
        inventory.select_product(_first_product(inventory_data))
        qty_per_box = float(inventory.value_of("qty_per_box"))
        inventory.set_value("box_qty", 3)
        inventory.field("box_qty").blur()
        expected = 3 * qty_per_box
        actual = float(inventory.value_of("total_qty"))
        assert actual == expected, f"Total Qty {actual} != Box Qty(3) x Qty/Box({qty_per_box}) = {expected}"

    @allure.story("Total Qty override recalculates Box Qty (spec 5.3)")
    @pytest.mark.regression
    def test_total_qty_override_recalculates_box_qty(self, inventory, inventory_data):
        inventory.select_product(_first_product(inventory_data))
        qty_per_box = float(inventory.value_of("qty_per_box"))
        inventory.set_value("total_qty", qty_per_box * 2)
        inventory.field("total_qty").blur()
        actual = float(inventory.value_of("box_qty"))
        assert actual == 2, f"Box Qty {actual} != Total Qty / Qty/Box = 2"

    @allure.story("Total BTP + VAT = BTP+VAT/Box x Box Qty (spec section 8)")
    @pytest.mark.regression
    def test_total_btp_vat_equals_price_per_box_times_box_qty(self, inventory, inventory_data):
        inventory.select_product(_first_product(inventory_data))
        price_per_box = float(inventory.value_of("price_per_box"))
        inventory.set_value("box_qty", 3)
        inventory.field("box_qty").blur()
        expected = round(price_per_box * 3, 2)
        actual = round(float(inventory.value_of("total_price")), 2)
        assert actual == expected, f"Total BTP+VAT {actual} != BTP+VAT/Box({price_per_box}) x Box Qty(3) = {expected}"

    @allure.story("Changing BTP+VAT/Box recalculates Total BTP + VAT")
    @pytest.mark.regression
    def test_price_per_box_change_recalculates_total(self, inventory, inventory_data):
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("box_qty", 2)
        inventory.field("box_qty").blur()
        inventory.set_value("price_per_box", 50)
        inventory.field("price_per_box").blur()
        actual = round(float(inventory.value_of("total_price")), 2)
        assert actual == 100.0, f"Total BTP+VAT {actual} != 50 x 2 = 100 after editing BTP+VAT/Box"

    @allure.story("A fully-valid item adds to the cart and updates Total Items / Total Price")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    @pytest.mark.regression
    def test_add_item_to_cart(self, inventory, inventory_data):
        before = inventory.total_items()
        inventory.add_item_to_cart(
            product=_first_product(inventory_data), box_qty=1, free_qty=0,
            batch_no="QA_AUTO_INV_DEFAULT",
        )
        assert inventory.total_items() == before + 1
        assert not inventory.cart_is_empty()

    @allure.story("Free Qty is included in the cart row but not treated as purchased (spec section 6)")
    @pytest.mark.regression
    def test_free_qty_shown_in_cart_row(self, inventory, inventory_data):
        product = _first_product(inventory_data)
        inventory.add_item_to_cart(product=product, box_qty=2, free_qty=7,
                                   batch_no="QA_AUTO_INV_FREEQTY")
        row = inventory.cart_row(inventory.cart_row_count() - 1)
        free_cell = row.locator("td").nth(5).inner_text().strip()  # Details/BoxQty/BTP+VAT/TotalPrice/ExpDate/Free/Action
        assert free_cell == "7", f"cart row Free column shows {free_cell!r}, expected '7'"

    @allure.story("Requirement gap (spec 45/102): a fractional Box Qty from a manually-set Total Qty is accepted")
    @allure.tag("requirement-gap")
    @pytest.mark.ui
    def test_fractional_box_qty_from_total_qty_override(self, inventory, inventory_data):
        """The spec explicitly flags this as needing confirmation before
        implementation (section 102 / item 48) - this test documents the
        CURRENT observed behaviour (fractional Box Qty IS accepted), it is not
        asserting a right/wrong outcome."""
        inventory.select_product(_first_product(inventory_data))
        qty_per_box = float(inventory.value_of("qty_per_box"))
        inventory.set_value("total_qty", qty_per_box * 2.5)
        inventory.field("total_qty").blur()
        box_qty = inventory.value_of("box_qty")
        allure.attach(f"Total Qty={qty_per_box * 2.5} -> Box Qty={box_qty!r}",
                      name="fractional box qty observed")
