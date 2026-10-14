"""Inventory Record - list + Inventory Details (spec sections 43-44).

BUG-INV-004 / BUG-INV-007 tests assert the SPEC-DESIRED behaviour and are
expected to stay red until those defects are fixed.
"""
from __future__ import annotations

import re

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage

pytestmark = [pytest.mark.inventory]


def _money(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", text)
    assert m, f"could not parse a money value out of {text!r}"
    return float(m.group().replace(",", ""))


def _eligible_and_free_qty_products(inventory_data: dict) -> tuple[str, str]:
    products = inventory_data.get("existing", {}).get("products_sample", ["100%", "TEST PRODUCT"])
    return products[0], (products[1] if len(products) > 1 else products[0])


@allure.epic("Inventory")
@allure.feature("Inventory Record")
class TestInventoryRecordList:

    @allure.story("A completed checkout appears at the top of Inventory Record")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    @pytest.mark.integration
    def test_completed_inventory_appears_in_record(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=1, batch_no="QA_AUTO_INV_REC_SMOKE")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        checkout.complete()

        record = InventoryRecordPage(inventory.page).open()
        assert record.row_count() >= 1, "no rows in Inventory Record after completing a checkout"
        first_row_bill = record.bill_amount_cell_text(record.row(0))
        allure.attach(first_row_bill, name="most recent record - Bill Amount cell")

    @allure.story("Inventory Details shows the correct product, batch, qty and price (spec section 44)")
    @pytest.mark.regression
    @pytest.mark.integration
    def test_inventory_details_reflects_the_line_item(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=4, batch_no="QA_AUTO_INV_REC_DETAILS")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        checkout.complete()

        record = InventoryRecordPage(inventory.page).open()
        dlg = record.open_details(0)
        assert dlg.inventory_id().startswith("#INV_"), f"unexpected Inventory ID {dlg.inventory_id()!r}"
        qty_cell = dlg.item_row(0).locator("td").nth(3).inner_text()
        assert "4" in qty_cell, f"item Qty cell {qty_cell!r} does not reflect Box Qty 4"
        dlg.close()


@allure.epic("Inventory")
@allure.feature("Discount vs. stored costing (BUG-INV-004 / BUG-INV-007)")
class TestDiscountCostingRegression:

    @allure.story("BUG-INV-004: an eligible line's stored Purchase Price should reflect its allocated discount")
    @allure.issue("BUG-INV-004")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_eligible_line_purchase_price_reflects_discount(self, inventory, inventory_data):
        eligible, free_qty_product = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=free_qty_product, box_qty=3, free_qty=5,
                                   batch_no="QA_AUTO_INV_REC_DISC_FREE")
        inventory.add_item_to_cart(product=eligible, box_qty=2,
                                   batch_no="QA_AUTO_INV_REC_DISC_ELIGIBLE")
        checkout = inventory.go_to_checkout()
        pre_discount_price_per_box = _money(
            [c for c in checkout.cart_table.column_values("BTP+VAT") if c][-1]
        ) if "BTP+VAT" in checkout.cart_table.headers() else None
        checkout.select_first_supplier()
        checkout.set_discount(10, "%")
        checkout.complete()

        record = InventoryRecordPage(inventory.page).open()
        dlg = record.open_details(0)
        # the eligible line was added SECOND -> it is item_row(1)
        purchase_price_text = dlg.item_purchase_price_text(1)
        purchase_price = _money(purchase_price_text)
        allure.attach(f"eligible line stored Purchase Price = {purchase_price_text!r}"
                      f"{'' if pre_discount_price_per_box is None else f' (pre-discount was {pre_discount_price_per_box})'}",
                      name="observed")
        assert pre_discount_price_per_box is None or purchase_price < pre_discount_price_per_box, (
            f"BUG-INV-004 reproduced: eligible line's stored Purchase Price ({purchase_price_text}) is "
            f"unchanged from its pre-discount BTP+VAT/Box ({pre_discount_price_per_box}) - the allocated "
            "discount was not reflected at the line-item / costing level"
        )
        dlg.close()

    @allure.story("BUG-INV-007: the list's discount badge should show the computed amount, not the entered rate")
    @allure.issue("BUG-INV-007")
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_record_list_discount_badge_shows_amount_not_rate(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=3, batch_no="QA_AUTO_INV_REC_BADGE")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        checkout.set_discount(10, "%")
        expected_amount = _money(checkout.discount_amount())
        checkout.complete()

        record = InventoryRecordPage(inventory.page).open()
        bill_text = record.bill_amount_cell_text(record.row(0))
        allure.attach(f"entered rate=10%, expected discount amount~={expected_amount}, "
                      f"Bill Amount cell={bill_text!r}", name="observed")
        m = re.search(r"-Tk\s*([\d,.]+)\s*disc", bill_text)
        assert m, f"no '-Tk N disc' badge found in Bill Amount cell {bill_text!r}"
        badge_value = float(m.group(1).replace(",", ""))
        assert badge_value == pytest.approx(expected_amount, abs=0.5), (
            f"BUG-INV-007 reproduced: discount badge shows {badge_value!r} (looks like the raw entered "
            f"rate, 10) instead of the computed discount amount (~{expected_amount})"
        )


@allure.epic("Inventory")
@allure.feature("Inventory Details required fields (BUG-INV-017, spec section 44.1)")
class TestInventoryDetailsRequiredFields:

    @allure.story("BUG-INV-017: Inventory Details must show every Pricing Breakdown row and Inventory Items column required by spec section 44.1")
    @allure.issue("BUG-INV-017")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_details_view_shows_all_required_fields_and_columns(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(
            product=eligible, box_qty=2, price_per_box=100,
            retail_price=150, wholesale_price=130, min_qty=25,
            rack_no="A1", batch_no="QA_AUTO_INV_DETAILS_FIELDS",
            barcode_value="QA9988776600",
        )
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        checkout.set_discount(10, "%")
        checkout.complete()

        record = InventoryRecordPage(inventory.page).open()
        dlg = record.open_details(0)
        missing_fields = dlg.missing_pricing_breakdown_fields()
        missing_columns = dlg.missing_item_columns()
        allure.attach(f"missing Pricing Breakdown fields: {missing_fields}\n"
                      f"missing Inventory Items columns: {missing_columns}", name="observed")
        assert not missing_fields and not missing_columns, (
            f"BUG-INV-017 reproduced: Inventory Details is missing required Pricing Breakdown "
            f"field(s) {missing_fields} and/or Inventory Items column(s) {missing_columns} per "
            "Inventory Management.md section 44.1, even though the backend API returns this data "
            "for the transaction (confirmed separately via network inspection)."
        )
        dlg.close()


@allure.epic("Inventory")
@allure.feature("Per-product discount allocation & display (BUG-INV-021)")
class TestPerProductDiscountAllocation:

    @allure.story("BUG-INV-021: a Percentage discount applied at Checkout must be allocated per "
                   "product (proportional to purchase price) and shown as a % on Inventory Details "
                   "- for both the backend record and the Details drawer UI")
    @allure.issue("BUG-INV-021")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_backend_and_ui_expose_per_product_discount_percentage(self, inventory, inventory_data):
        eligible, other = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=1, price_per_box=100,
                                   batch_no="QA_AUTO_INV_PCT_DISC_1")
        inventory.add_item_to_cart(product=other, box_qty=1, price_per_box=110,
                                   batch_no="QA_AUTO_INV_PCT_DISC_2")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        checkout.set_discount(10, "%")
        discount_amount_shown = _money(checkout.discount_amount())
        checkout.complete()

        record = InventoryRecordPage(inventory.page).open()
        dlg, raw = record.open_details_capturing_api(0)
        missing_columns = dlg.missing_item_columns()
        raw_items = raw.get("items", [])
        discount_keys = {"discountAmount", "discountPercent", "discountValue",
                          "itemDiscountAmount", "discountPercentage"}
        items_with_discount = [it for it in raw_items if discount_keys & it.keys()]

        allure.attach(
            f"checkout Discount Amount shown={discount_amount_shown}\n"
            f"missing UI columns: {missing_columns}\n"
            f"raw item keys sample: {list(raw_items[0].keys()) if raw_items else 'none'}\n"
            f"items carrying a discount field: {len(items_with_discount)} / {len(raw_items)}",
            name="observed",
        )
        assert raw_items and "Discount" not in missing_columns and len(items_with_discount) == len(raw_items), (
            "BUG-INV-021 reproduced: a Percentage discount applied at Checkout (10%, Discount "
            f"Amount correctly computed as {discount_amount_shown}) is never allocated per product "
            "anywhere. The raw API response for the completed inventory carries the discount only "
            "at the header level (discountAmount/discountType/discountValue) - none of the item "
            "records in items[] carry any discount field - so the Inventory Details 'Discount' "
            "column (itself still missing from the UI) has no data to render even if it existed. "
            "Per spec section 39/44.1, each eligible product's allocated share must be computed, "
            "persisted, and displayed as a percentage of that product's purchase price."
        )
        dlg.close()
