"""Inventory - Opening Stock mode (spec sections 14-21).

BUG-INV-005 / BUG-INV-006 were closed as accepted behaviour by the product owner (2026-10-12): a manual
BTP+VAT/Box does not back-calculate the %, and a later Retail edit re-derives BTP+VAT/Box.
"""
from __future__ import annotations

import allure
import pytest

from utils.constants import INVENTORY_OPENING_STOCK_DEFAULT_PERCENT

pytestmark = [pytest.mark.inventory]


def _first_product(inventory_data: dict) -> str:
    return inventory_data.get("existing", {}).get("products_sample", ["TEST PRODUCT"])[0]


@allure.epic("Inventory")
@allure.feature("Opening Stock mode")
class TestOpeningStockMode:

    @allure.story(f"Opening Stock (%) defaults to {INVENTORY_OPENING_STOCK_DEFAULT_PERCENT} on mode select (spec section 15)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_default_percent_is_12(self, inventory):
        inventory.switch_mode("Opening Stock")
        pct = inventory.value_of("opening_stock_percent")
        assert pct == str(INVENTORY_OPENING_STOCK_DEFAULT_PERCENT), \
            f"Opening Stock (%) defaulted to {pct!r}, expected {INVENTORY_OPENING_STOCK_DEFAULT_PERCENT!r}"

    @allure.story("Selecting a product auto-calculates BTP+VAT/Box from Retail Price (spec section 16)")
    @pytest.mark.smoke
    def test_product_select_precalculates_btp_vat(self, inventory, inventory_data):
        inventory.switch_mode("Opening Stock")
        inventory.select_product(_first_product(inventory_data))
        retail = inventory.value_of("retail_price")
        btp = inventory.value_of("price_per_box")
        assert retail not in ("", "0"), "Retail Price/Box was not preloaded"
        assert btp not in ("", "0"), "BTP+VAT/Box was not auto-calculated from Retail Price"

    @allure.story("Total BTP + VAT = BTP+VAT/Box x Box Qty (spec section 18)")
    @pytest.mark.regression
    def test_total_reflects_price_per_box_times_box_qty(self, inventory, inventory_data):
        inventory.switch_mode("Opening Stock")
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("box_qty", 10)
        inventory.field("box_qty").blur()
        price_per_box = float(inventory.value_of("price_per_box"))
        expected = round(price_per_box * 10, 2)
        actual = round(float(inventory.value_of("total_price")), 2)
        assert actual == expected, f"Total BTP+VAT {actual} != BTP+VAT/Box({price_per_box}) x 10 = {expected}"

    @allure.story("Manual override of BTP+VAT/Box is honoured for Total BTP + VAT (spec section 19)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_manual_btp_override_total_updates(self, inventory, inventory_data):
        inventory.switch_mode("Opening Stock")
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("box_qty", 10)
        inventory.field("box_qty").blur()
        inventory.set_value("price_per_box", 80)
        inventory.field("price_per_box").blur()
        total = round(float(inventory.value_of("total_price")), 2)
        assert total == 800.0, f"Total BTP+VAT {total} != manual BTP+VAT/Box(80) x Box Qty(10) = 800"

    @allure.story("Accepted behaviour: a manual BTP+VAT/Box override does not change Opening Stock (%)")
    @pytest.mark.regression
    def test_manual_btp_override_leaves_percent(self, inventory, inventory_data):
        inventory.switch_mode("Opening Stock")
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("retail_price", 100)
        inventory.field("retail_price").blur()
        inventory.set_value("box_qty", 10)
        inventory.field("box_qty").blur()
        before = inventory.value_of("opening_stock_percent")
        inventory.set_value("price_per_box", 80)
        inventory.field("price_per_box").blur()
        assert inventory.value_of("opening_stock_percent") == before

    @allure.story("Accepted behaviour: editing Retail Price after a manual BTP+VAT/Box re-derives BTP+VAT/Box")
    @pytest.mark.regression
    def test_retail_price_edit_rederives_btp(self, inventory, inventory_data):
        inventory.switch_mode("Opening Stock")
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("retail_price", 100)
        inventory.field("retail_price").blur()
        inventory.set_value("box_qty", 10)
        inventory.field("box_qty").blur()
        inventory.set_value("price_per_box", 80)
        inventory.field("price_per_box").blur()
        inventory.set_value("retail_price", 150)
        inventory.field("retail_price").blur()
        pct = float(inventory.value_of("opening_stock_percent") or 12)
        assert float(inventory.value_of("price_per_box")) == round(150 * (1 - pct / 100), 2)

    @allure.story("A valid Opening Stock line adds to the cart")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.regression
    @pytest.mark.integration
    def test_add_opening_stock_item_to_cart(self, inventory, inventory_data):
        inventory.switch_mode("Opening Stock")
        before = inventory.total_items()
        inventory.select_product(_first_product(inventory_data))
        inventory.set_value("box_qty", 5)
        inventory.field("box_qty").blur()
        inventory.set_value("batch_no", "QA_AUTO_INV_OPENSTOCK")
        inventory.submit_cart_item()
        assert inventory.total_items() == before + 1
