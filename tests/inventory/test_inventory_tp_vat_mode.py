"""Inventory - TP/VAT mode: automatic VAT calculation + optional TP/VAT
(spec sections 10-13)."""
from __future__ import annotations

import allure
import pytest

from utils.constants import INVENTORY_SYSTEM_VAT_PERCENT

pytestmark = [pytest.mark.inventory]


def _first_product(inventory_data: dict) -> str:
    return inventory_data.get("existing", {}).get("products_sample", ["TEST PRODUCT"])[0]


@allure.epic("Inventory")
@allure.feature("TP/VAT mode")
class TestTpVatMode:

    @allure.story("Switching to TP/VAT mode shows TP/Box and VAT/Box, both optional")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_mode_switch_shows_tp_vat_fields(self, inventory):
        inventory.switch_mode("TP/VAT")
        assert inventory.current_mode() == "TP/VAT"
        assert inventory.field("tp_per_box").count() == 1
        assert inventory.field("vat_per_box").count() == 1
        # neither carries the required asterisk (spec section 12)
        tp_label = inventory.page.locator("label", has_text="TP/Box")
        vat_label = inventory.page.locator("label", has_text="VAT/Box")
        assert "ant-form-item-required" not in (tp_label.first.get_attribute("class") or "")
        assert "ant-form-item-required" not in (vat_label.first.get_attribute("class") or "")

    @allure.story(f"TP/Box auto-calculates VAT/Box at the system rate ({INVENTORY_SYSTEM_VAT_PERCENT}%)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_tp_box_autocalculates_vat(self, inventory, inventory_data):
        inventory.switch_mode("TP/VAT")
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("tp_per_box", 100)
        inventory.field("tp_per_box").blur()
        expected = round(100 * INVENTORY_SYSTEM_VAT_PERCENT / 100, 2)
        actual = round(float(inventory.value_of("vat_per_box")), 2)
        assert actual == expected, f"VAT/Box {actual} != 100 x {INVENTORY_SYSTEM_VAT_PERCENT}% = {expected}"

    @allure.story("Manually changing VAT/Box does NOT modify TP/Box (spec section 11)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_manual_vat_does_not_change_tp(self, inventory, inventory_data):
        inventory.switch_mode("TP/VAT")
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("tp_per_box", 100)
        inventory.field("tp_per_box").blur()
        inventory.set_value("vat_per_box", 5)
        inventory.field("vat_per_box").blur()
        tp = inventory.value_of("tp_per_box")
        assert tp == "100", f"TP/Box changed to {tp!r} after manually editing VAT/Box - should stay 100"

    @allure.story("TP/Box = 0 with a manual VAT/Box is a valid, addable line (spec section 12)")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.regression
    @pytest.mark.integration
    def test_tp_zero_is_allowed(self, inventory, inventory_data):
        inventory.switch_mode("TP/VAT")
        before = inventory.total_items()
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("tp_per_box", 0)
        inventory.field("tp_per_box").blur()
        inventory.set_value("vat_per_box", 5)
        inventory.field("vat_per_box").blur()
        inventory.set_value("box_qty", 2)
        inventory.field("box_qty").blur()
        inventory.set_value("batch_no", "QA_AUTO_INV_TPZERO")
        inventory.submit_cart_item()
        assert inventory.total_items() == before + 1, "TP/Box = 0 line was not accepted into the cart"

    @allure.story("Total Price for a TP/VAT line = (TP/Box + VAT/Box) x Box Qty (spec section 13)")
    @pytest.mark.regression
    def test_total_price_formula(self, inventory, inventory_data):
        inventory.switch_mode("TP/VAT")
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("tp_per_box", 15)
        inventory.field("tp_per_box").blur()
        inventory.set_value("vat_per_box", 10)
        inventory.field("vat_per_box").blur()
        inventory.set_value("box_qty", 2)
        inventory.field("box_qty").blur()
        inventory.set_value("batch_no", "QA_AUTO_INV_TPVAT_TOTAL")
        before_total = inventory.cart_total_price_text()
        inventory.submit_cart_item()
        row = inventory.cart_row(inventory.cart_row_count() - 1)
        total_price_cell = row.locator("td").nth(4).inner_text().strip()  # Details/BoxQty/TP/VAT/TotalPrice
        assert "50" in total_price_cell, (
            f"Total Price cell {total_price_cell!r} - expected (15+10) x 2 = 50; "
            f"cart total before this add was {before_total!r}"
        )
