"""Default mode - 'Add Items to Cart' create form (spec sections 3-8, 20-26, 46).

Everything here exercises ONE screen: the create form. Cart / checkout / record
are covered in the sibling modules. Tests that assert a spec rule the current
build violates are tied to the logged defect (BUG-INV-xxx) and stay red until
it is fixed (same convention as the rest of the inventory suite).
"""
from __future__ import annotations

import allure
import pytest

from utils.inventory_assertions import Verifier, check_form_after_entry
from utils.inventory_calc import Line

pytestmark = [pytest.mark.inventory, pytest.mark.ui]

ALL_FIELDS = ("company", "product", "box_qty", "qty_per_box", "total_qty", "free_qty", "total_price", "price_per_box",
              "retail_price", "wholesale_price", "min_qty", "rack_no", "storage_type", "batch_no", "expiry_date",
              "barcode_value")


def _blur(inv, key):
    inv.field(key).blur()


@allure.epic("Inventory")
@allure.feature("Default mode - create form")
class TestFormStructure:

    @allure.story("Panel opens by default in Default mode with every spec field (spec 3, 7.2)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_all_fields_present(self, default_inventory):
        inv = default_inventory
        assert inv.current_mode() == "Default" and inv.panel_open()
        missing = [k for k in ALL_FIELDS if inv.field(k).count() != 1]
        assert not missing, f"fields missing in Default mode: {missing}"

    @allure.story("Default mode shows BTP+VAT fields, not TP/VAT fields (modes independent, spec 47.1)")
    def test_no_tp_vat_fields(self, default_inventory):
        for sel in ("#tpPerBox", "#vatPerBox", "#openingStockPercent"):
            assert default_inventory.page.locator(sel).count() == 0, f"{sel} must not exist in Default mode"

    @allure.story("Total Qty and Total BTP+VAT are derived values")
    def test_initial_state_before_product(self, default_inventory):
        snap = default_inventory.form_snapshot()
        assert snap.get("product", "") == "" and snap.get("box_qty", "") in ("", "0")

    @allure.story("Submit button reads 'Add Items to Cart' in create mode (spec 27)")
    def test_submit_button_label(self, default_inventory):
        assert default_inventory.submit_button().inner_text().strip() == "Add Items to Cart"
        assert not default_inventory.is_edit_mode()


@allure.epic("Inventory")
@allure.feature("Default mode - create form")
class TestDrawerStatePerMode:

    @allure.story("Closing the panel in Default is remembered for Default only (spec 3)")
    @pytest.mark.regression
    def test_panel_state_independent_per_mode(self, default_inventory):
        inv = default_inventory
        inv.close_add_items_panel()
        assert not inv.panel_open()
        inv.switch_mode("TP/VAT")
        assert inv.panel_open(), "TP/VAT panel must still be open when only Default was closed"
        inv.switch_mode("Default")
        assert not inv.panel_open(), "Default panel must stay closed when returning to it"
        inv.open_add_items_panel()
        assert inv.panel_open()

    @allure.story("Changing mode swaps the purchase-price fields")
    def test_mode_switch_changes_fields(self, default_inventory):
        inv = default_inventory
        inv.switch_mode("TP/VAT")
        inv.field("tp_per_box").wait_for(state="visible")
        assert inv.field("tp_per_box").count() == 1
        inv.switch_mode("Default")
        assert inv.field("price_per_box").count() == 1 and inv.page.locator("#tpPerBox").count() == 0


@allure.epic("Inventory")
@allure.feature("Default mode - create form")
class TestProductSelection:

    @pytest.mark.parametrize("ref", ["P0", "P1", "P2"])
    @allure.story("Selecting a product loads Qty/Box, Retail/Wholesale and BTP+VAT defaults (spec 4)")
    @pytest.mark.regression
    def test_defaults_loaded(self, default_inventory, ref):
        inv = default_inventory
        inv.select_product(inv.resolve_product(ref), exact=True)
        snap = inv.form_snapshot()
        v = Verifier(f"product {ref} defaults")
        v.true("Qty/Box loaded and > 0", float(snap["qty_per_box"] or 0) > 0, snap["qty_per_box"])
        v.true("Retail Price/Box loaded", snap["retail_price"] != "", snap["retail_price"])
        v.true("Wholesale Price/Box loaded", snap["wholesale_price"] != "", snap["wholesale_price"])
        if ref == "P2":   # '3 BION' has NO stored purchase price: BTP+VAT/Box stays empty and must be typed (see BUG-INV-029)
            v.true("BTP+VAT/Box is empty for a product with no stored price", snap["price_per_box"] == "", snap["price_per_box"])
        else:
            v.true("BTP+VAT/Box loaded", snap["price_per_box"] != "", snap["price_per_box"])
        v.assert_all()

    @allure.story("Selecting a product does not disturb entered quantity logic: Total = Box x Qty/Box")
    def test_switching_product_recalculates(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 2); _blur(inv, "box_qty")
        inv.select_product(inv.resolve_product("P1"), exact=True)
        inv.set_value("box_qty", 2); _blur(inv, "box_qty")
        assert inv.form_number("total_qty") == 2 * inv.form_number("qty_per_box")


@allure.epic("Inventory")
@allure.feature("Default mode - create form")
class TestQuantityLogic:

    @pytest.mark.parametrize("box", [1, 2, 3, 7, 10, 25, 100, 0.5, 1.5])
    @allure.story("Total Qty = Box Qty x Qty/Box for whole and fractional boxes (spec 5.3)")
    @pytest.mark.regression
    def test_box_to_total(self, default_inventory, box):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", box); _blur(inv, "box_qty")
        assert inv.form_number("total_qty") == pytest.approx(box * inv.form_number("qty_per_box"))

    @pytest.mark.parametrize("pieces", [1, 5, 10, 15, 25, 99])
    @allure.story("Total Qty override recalculates Box Qty, fractional allowed and NOT rounded (spec 5.3)")
    @pytest.mark.regression
    def test_total_to_box_fractional(self, default_inventory, pieces):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        qpb = inv.form_number("qty_per_box")
        inv.set_value("total_qty", pieces); _blur(inv, "total_qty")
        assert inv.form_number("box_qty") == pytest.approx(pieces / qpb, rel=1e-6), \
            f"Box Qty must be exactly Total/Qty-per-Box ({pieces}/{qpb}), not rounded"

    @allure.story("Free Qty does not change Total Qty (purchased) or Total BTP+VAT (spec 6, 32)")
    def test_free_qty_not_purchased(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("price_per_box", 50); inv.set_value("box_qty", 3); _blur(inv, "box_qty")
        before = (inv.form_number("total_qty"), inv.form_number("total_price"))
        inv.set_value("free_qty", 10); _blur(inv, "free_qty")
        assert (inv.form_number("total_qty"), inv.form_number("total_price")) == before


@allure.epic("Inventory")
@allure.feature("Default mode - create form")
class TestBtpVatSync:

    @pytest.mark.parametrize("box,price", [(1, 50), (3, 50), (2, 33.3), (10, 125.75), (7, 0.01), (0.5, 100), (250, 7.2)])
    @allure.story("BTP+VAT/Box change recalculates Total BTP+VAT (spec 8)")
    @pytest.mark.regression
    def test_per_box_to_total(self, default_inventory, box, price):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", box); inv.set_value("price_per_box", price); _blur(inv, "price_per_box")
        v = Verifier("per-box -> total")
        check_form_after_entry(v, inv.form_snapshot(), Line(box, inv.form_number("qty_per_box"), price))
        v.assert_all()

    @pytest.mark.parametrize("box,total", [(2, 100), (3, 150), (4, 100.4), (10, 1257.5)])
    @allure.story("Total BTP+VAT change recalculates BTP+VAT/Box = Total / Box Qty (spec 8)")
    @pytest.mark.regression
    def test_total_to_per_box(self, default_inventory, box, total):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", box); _blur(inv, "box_qty")
        inv.set_value("total_price", total); _blur(inv, "total_price")
        assert inv.form_number("price_per_box") == pytest.approx(total / box, abs=0.011)

    @allure.story("Changing Box Qty after the price keeps BTP+VAT/Box and updates the Total")
    def test_box_change_after_price(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("price_per_box", 40); inv.set_value("box_qty", 2); _blur(inv, "box_qty")
        inv.set_value("box_qty", 5); _blur(inv, "box_qty")
        assert inv.form_number("price_per_box") == pytest.approx(40)
        assert inv.form_number("total_price") == pytest.approx(200)

    @allure.story("Zero BTP+VAT/Box is accepted as a valid zero-cost entry (spec 41, 46)")
    @pytest.mark.negative
    def test_zero_price_accepted(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 2); inv.set_value("price_per_box", 0); _blur(inv, "price_per_box")
        assert inv.form_number("total_price") == 0
        assert inv.try_add_to_cart(), "a zero-cost line must be addable (spec 46: TP=0 / VAT=0 allowed)"


@allure.epic("Inventory")
@allure.feature("Default mode - create form")
class TestValidation:

    @allure.story("Product is required (spec 46)")
    @pytest.mark.negative
    def test_product_required(self, default_inventory):
        inv = default_inventory
        inv.set_value("box_qty", 2)
        assert not inv.try_add_to_cart(), "item without a product must not be added"

    @pytest.mark.parametrize("text", ["", "-", "abc"])
    @allure.story("Box Qty is required: empty / non-numeric input is blocked with 'Box qty is required'")
    @pytest.mark.negative
    def test_box_qty_required(self, default_inventory, text):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.type_value("box_qty", text)
        assert not inv.try_add_to_cart(), f"Box Qty {text!r} must be rejected"
        assert any("box qty is required" in e.lower() for e in inv.form_errors()), inv.form_errors()

    @pytest.mark.parametrize("key,text", [
        ("box_qty", "-1"), ("box_qty", "-0.5"), ("free_qty", "-1"), ("free_qty", "-10"),
        ("price_per_box", "-5"), ("retail_price", "-10"), ("min_qty", "-3"),
    ])
    @allure.story("Negative numbers cannot be entered: typing '-' + digits leaves 0 in the field (spec 46)")
    @pytest.mark.negative
    def test_negative_input_is_clamped_to_zero(self, default_inventory, key, text):
        """Verified by hand + live probe (2026-10-08): the inputs clamp a typed negative to 0, with no message.
        (The earlier version of this test used fill(), which bypasses key handling, and wrongly reported
        negatives as accepted.)"""
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        shown = inv.type_value(key, text)
        assert float(shown or 0) >= 0, f"{key}: typed {text!r} left a NEGATIVE value {shown!r} in the field"
        assert shown in ("0", "0.0", ""), f"{key}: typed {text!r}, expected the field to hold 0, got {shown!r}"

    @pytest.mark.parametrize("free", [0, 5])
    @allure.story("Box Qty must be greater than 0: a line with 0 boxes is rejected, with or without Free Qty (confirmed 2026-10-08)")
    @allure.issue("BUG-INV-030")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.negative
    def test_box_qty_must_be_greater_than_zero(self, default_inventory, free):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.type_value("box_qty", "0")
        if free:
            inv.set_value("free_qty", free)
        added = inv.try_add_to_cart()
        if inv.cart_row_count():
            inv.clear_cart()
        assert not added, f"BUG-INV-030: a line with Box Qty 0 (Free Qty {free}) was added to the cart"

    @allure.story("Past dates are NOT disabled in the Expiry Date calendar - intentional (confirmed 2026-10-08)")
    def test_past_dates_not_disabled(self, default_inventory):
        assert default_inventory.expiry_past_dates_disabled() is not True, "past dates are disabled in the Expiry Date picker"

    @allure.story("An item with a past Expiry Date is accepted into the cart - intentional (confirmed 2026-10-08)")
    def test_past_expiry_accepted(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 1)
        inv.set_expiry_date(1, "Jan", 2026)
        assert "2026" in inv.expiry_date_text()
        added = inv.try_add_to_cart()
        if inv.cart_row_count():
            inv.clear_cart()
        assert added, "an item with a past Expiry Date was rejected"

    @allure.story("Storage 'Rack' takes a text value")
    def test_storage_rack_has_input(self, default_inventory):
        inv = default_inventory
        inv.select_storage_type("Rack")
        assert inv.field_is_enabled("rack_no")

    @allure.story("Storage 'WHS' has no input: a pharmacy has one warehouse, so the field is intentionally disabled (confirmed 2026-10-08)")
    def test_storage_whs_has_no_input(self, default_inventory):
        inv = default_inventory
        inv.select_storage_type("WHS")
        assert not inv.field_is_enabled("rack_no"), "the storage text input must be disabled for WHS"
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 1)
        added = inv.try_add_to_cart()
        if inv.cart_row_count():
            inv.clear_cart()
        assert added, "an item with WHS storage (no location text) could not be added"

    @allure.story("Empty Batch No is allowed - the system generates one (spec 24, 46)")
    def test_empty_batch_allowed(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 1)
        assert inv.try_add_to_cart(), "an item with no Batch No must be accepted"

    @allure.story("No Expiry Date is allowed - batch is valid for life (spec 25)")
    def test_no_expiry_allowed(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 1); inv.set_value("batch_no", "QA_NOEXP")
        assert inv.expiry_date_text() == "" and inv.try_add_to_cart()

    @allure.story("Valid future Expiry Date is accepted and shown")
    def test_future_expiry_accepted(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 1); inv.set_expiry_date(15, "Dec", 2035)
        assert "2035" in inv.expiry_date_text()
        assert inv.try_add_to_cart()

    @pytest.mark.parametrize("min_qty", [0, 1, 20, 1000])
    @allure.story("Min Qty >= 0 is accepted (spec 22, 46)")
    def test_min_qty_valid(self, default_inventory, min_qty):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 1); inv.set_value("min_qty", min_qty)
        assert inv.try_add_to_cart()

    @allure.story("Barcode value is accepted and carried to the cart (spec 26)")
    def test_barcode_value(self, default_inventory, run_tag):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 1); inv.set_value("barcode_value", f"8{run_tag}")
        assert inv.value_of("barcode_value") == f"8{run_tag}"


@allure.epic("Inventory")
@allure.feature("Default mode - create form")
class TestAfterSubmit:

    @allure.story("Form resets after Add Items to Cart so a second line can be entered (spec 27-28)")
    def test_form_resets_after_add(self, default_inventory):
        inv = default_inventory
        inv.add_item_to_cart(product=inv.resolve_product("P0"), box_qty=2, batch_no="QA_RESET")
        snap = inv.form_snapshot()
        assert snap["batch_no"] == "" and snap["box_qty"] in ("", "0"), f"form not reset: {snap}"

    @allure.story("Business rule: the same product cannot be added twice (message: already in the cart)")
    def test_same_product_blocked(self, default_inventory):
        inv = default_inventory
        inv.add_item_to_cart(product=inv.resolve_product("P0"), box_qty=1, batch_no="QA_DUP_A")
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 2); inv.set_value("batch_no", "QA_DUP_B")
        assert not inv.try_add_to_cart(), "a product already in the cart must not be added again"
        assert inv.total_items() == 1
        assert any("already in the cart" in t.lower() for t in inv.messages())

    @allure.story("Fractional Box Qty is accepted end-to-end into the cart (spec 5.3)")
    def test_fractional_box_added(self, default_inventory):
        inv = default_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        qpb = inv.form_number("qty_per_box")
        inv.set_value("total_qty", qpb / 2); _blur(inv, "total_qty")
        assert inv.form_number("box_qty") == pytest.approx(0.5)
        assert inv.try_add_to_cart()
