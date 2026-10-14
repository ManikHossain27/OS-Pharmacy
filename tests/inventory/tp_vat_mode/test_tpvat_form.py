"""TP/VAT mode - 'Add Items to Cart' create form (spec sections 10-13, 20-26, 38, 41, 46).

Everything here exercises ONE screen: the create form (plus the cart row it produces).
Nothing is completed, so no stock / financial data is created.
Facts verified live 2026-10-11: TP/Box and VAT/Box are pre-filled from the product; typing TP/Box re-derives
VAT/Box at 17.4 % (100 -> 17.4, 89.44 -> 15.56); typing VAT/Box never changes TP/Box; the form has a
'Special Discount (Tk)' field (id specialDiscountValue); VAT is charged on free pieces too.
"""
from __future__ import annotations

import allure
import pytest

from utils.tpvat_calc import SYSTEM_VAT_RATE, vat_for

pytestmark = [pytest.mark.inventory, pytest.mark.ui]

ALL_FIELDS = ("company", "product", "box_qty", "qty_per_box", "total_qty", "free_qty", "tp_per_box", "vat_per_box",
              "retail_price", "wholesale_price", "min_qty", "rack_no", "storage_type", "batch_no", "expiry_date",
              "barcode_value", "special_discount")


def _fill(inv, *, tp=None, vat=None, box=1, free=None, special=None, product="P0"):
    inv.select_product(inv.resolve_product(product), exact=True)
    if tp is not None:
        inv.set_value("tp_per_box", tp)
        inv.field("tp_per_box").blur()
        inv.page.wait_for_timeout(250)
    if vat is not None:
        inv.set_value("vat_per_box", vat)
        inv.field("vat_per_box").blur()
    inv.set_value("box_qty", box)
    inv.field("box_qty").blur()
    if free:
        inv.set_value("free_qty", free)
        inv.field("free_qty").blur()
    if special is not None:
        inv.type_value("special_discount", str(special))


def _add(inv, flow, **kw) -> bool:
    _fill(inv, **kw)
    inv.set_value("batch_no", flow.next_batch("T"))
    return inv.try_add_to_cart()


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - create form")
class TestFormStructure:

    @allure.story("TP/VAT mode opens with every spec field plus Special Discount (Tk) (spec 10.2)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_all_fields_present(self, tpvat_inventory):
        inv = tpvat_inventory
        assert inv.current_mode() == "TP/VAT" and "inventory/tp-vat" in inv.page.url
        missing = [k for k in ALL_FIELDS if inv.field(k).count() != 1]
        assert not missing, f"fields missing in TP/VAT mode: {missing}"

    @allure.story("TP/VAT mode does not show the Default / Opening Stock price fields (modes independent)")
    def test_no_other_mode_fields(self, tpvat_inventory):
        for sel in ("#btpVatPerBox", "#totalItemPrice", "#openingStockPercent"):
            assert tpvat_inventory.page.locator(sel).count() == 0, f"{sel} must not exist in TP/VAT mode"

    @allure.story("The VAT/Box label states the system VAT rate (17.4 %) (spec 11)")
    def test_vat_label_shows_rate(self, tpvat_inventory):
        labels = [t.strip() for t in tpvat_inventory.page.locator("label").all_inner_texts()]
        assert any(l.startswith("VAT/Box") and f"{SYSTEM_VAT_RATE * 100:g}%" in l.replace(" ", "") for l in labels), labels

    @allure.story("TP/Box and VAT/Box are optional - no required asterisk; Product and Box Qty are required (spec 12)")
    def test_required_markers(self, tpvat_inventory):
        page = tpvat_inventory.page
        def required(text):
            lab = page.locator("label", has_text=text).first
            return "ant-form-item-required" in (lab.get_attribute("class") or "")
        assert not required("TP/Box") and not required("VAT/Box")
        assert required("Product") and required("Box Qty")

    @allure.story("Submit button reads 'Add Items to Cart' in create mode (spec 27)")
    def test_submit_button_label(self, tpvat_inventory):
        assert tpvat_inventory.submit_button().inner_text().strip() == "Add Items to Cart"
        assert not tpvat_inventory.is_edit_mode()


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - create form")
class TestVatCalculation:

    @allure.story("Selecting a product pre-fills TP/Box and VAT/Box (VAT at the system rate of the TP)")
    @pytest.mark.regression
    def test_product_preloads_tp_and_vat(self, tpvat_inventory):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        tp, vat = inv.form_number("tp_per_box"), inv.form_number("vat_per_box")
        assert tp > 0, "TP/Box not pre-filled from the product"
        assert vat == pytest.approx(vat_for(tp), abs=0.011), f"preloaded VAT {vat} is not 17.4 % of TP {tp}"

    @pytest.mark.parametrize("tp", [0.01, 1, 10, 33.3, 89.44, 100, 125.75, 612, 999.99, 12345.67])
    @allure.story("Typing TP/Box auto-calculates VAT/Box = TP x 17.4 % (spec 11)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_tp_autocalculates_vat(self, tpvat_inventory, tp):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("tp_per_box", tp)
        inv.field("tp_per_box").blur()
        inv.page.wait_for_timeout(300)
        assert inv.form_number("vat_per_box") == pytest.approx(vat_for(tp), abs=0.011), \
            f"TP {tp}: VAT/Box {inv.value_of('vat_per_box')!r} != {vat_for(tp)}"

    @pytest.mark.parametrize("vat", [0, 5, 17.4, 99.99])
    @allure.story("A manually entered VAT/Box is accepted and does NOT change TP/Box (spec 11)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_manual_vat_keeps_tp(self, tpvat_inventory, vat):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("tp_per_box", 100)
        inv.field("tp_per_box").blur()
        inv.set_value("vat_per_box", vat)
        inv.field("vat_per_box").blur()
        inv.page.wait_for_timeout(300)
        assert inv.form_number("vat_per_box") == pytest.approx(vat, abs=0.011), "manual VAT was not kept"
        assert inv.form_number("tp_per_box") == 100, "TP/Box changed after VAT/Box was edited (spec 11)"

    @allure.story("Editing TP/Box after a manual VAT re-derives VAT/Box at the system rate (observed rule)")
    def test_tp_edit_rederives_vat(self, tpvat_inventory):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("tp_per_box", 100)
        inv.field("tp_per_box").blur()
        inv.set_value("vat_per_box", 5)
        inv.field("vat_per_box").blur()
        inv.set_value("tp_per_box", 89.44)
        inv.field("tp_per_box").blur()
        inv.page.wait_for_timeout(300)
        assert inv.form_number("vat_per_box") == pytest.approx(vat_for(89.44), abs=0.011)
        assert inv.form_number("tp_per_box") == 89.44

    @pytest.mark.parametrize("box,qty_per_box_expected", [(1, 10), (2, 10), (7, 10), (0.5, 10), (250, 10)])
    @allure.story("Total Qty = Box Qty x Qty/Box (spec 5.3)")
    def test_total_qty(self, tpvat_inventory, box, qty_per_box_expected):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        qpb = inv.form_number("qty_per_box")
        inv.set_value("box_qty", box)
        inv.field("box_qty").blur()
        inv.page.wait_for_timeout(300)
        assert inv.form_number("total_qty") == pytest.approx(box * qpb)

    @allure.story("Typing Total Qty derives Box Qty (spec 45: Total Qty -> Box Qty)")
    def test_total_qty_drives_box_qty(self, tpvat_inventory):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        qpb = inv.form_number("qty_per_box")
        inv.set_value("total_qty", qpb * 3)
        inv.field("total_qty").blur()
        inv.page.wait_for_timeout(300)
        assert inv.form_number("box_qty") == pytest.approx(3)


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - create form")
class TestAddToCart:

    @allure.story("Cart row = TP/Box, VAT/Box and Total Price (TP + VAT) x Box Qty (spec 13): 89.44 + 15.56 = 105 x 2 = 210")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_total_price_formula(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=89.44, box=2)
        row = inv.cart_rows()[0]
        assert "89.44" in row["TP/Box"] and "15.56" in row["VAT/Box"]
        assert "210.00" in row["Total Price"] and inv.cart_total_price() == pytest.approx(210.0)

    @allure.story("Spec 12 / 41: TP/Box = 0 with a VAT/Box is accepted; Total Price = VAT x boxes")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.regression
    def test_tp_zero_with_vat_is_accepted(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=0, vat=5, box=2), "TP/Box = 0 with VAT/Box 5 was rejected (spec 12/41)"
        assert inv.cart_total_price() == pytest.approx(10.0)

    @allure.story("Spec 12: VAT/Box = 0 with a TP/Box is accepted; Total Price = TP x boxes")
    @pytest.mark.regression
    def test_vat_zero_with_tp_is_accepted(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=100, vat=0, box=2), "VAT/Box = 0 was rejected (spec 12)"
        assert inv.cart_total_price() == pytest.approx(200.0)

    @allure.story("Spec 12: TP/Box and VAT/Box are both optional - a line with neither is not rejected for that reason")
    @pytest.mark.regression
    def test_both_zero_is_accepted(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=0, vat=0, box=1), "TP/Box = 0 and VAT/Box = 0 was rejected although both are optional (spec 12)"
        assert inv.cart_total_price() == pytest.approx(0.0)

    @allure.story("Free pieces carry VAT: (15 + 10) x 2 + 1.00 x 10 free = Tk 60 (sheet AC; verified live)")
    @pytest.mark.regression
    def test_free_qty_adds_vat_to_total(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=15, vat=10, box=2, free=10)
        row = inv.cart_rows()[0]
        assert "60.00" in row["Total Price"] and row["Free"].strip() == "10"

    @allure.story("Special Discount (Tk) is accepted and shown in the cart as 'Tk 20.00 / SP.Dis / 10.00%' (10 % of TP 200)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_special_discount_in_cart(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=100, box=2, special=20)
        cell = inv.cart_rows()[0]["Discount"]
        assert "SP.Dis" in cell and "20.00" in cell and "10.00%" in cell, cell

    @allure.story("Business rule: a product can be in the cart ONCE - a second add is refused with a message")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_same_product_cannot_be_added_twice(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=89.44, box=2)
        _fill(inv, tp=50, box=5)
        inv.set_value("batch_no", flow.next_batch("T"))
        assert not inv.try_add_to_cart() and inv.total_items() == 1
        assert any("already in the cart" in m.lower() for m in inv.messages()), inv.messages()

    @pytest.mark.parametrize("free", [0, 5])
    @allure.story("Box Qty must be greater than 0 (confirmed 2026-10-08; same rule as Default mode)")
    @allure.issue("BUG-INV-030")
    @pytest.mark.negative
    def test_box_qty_must_be_greater_than_zero(self, tpvat_inventory, free):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.type_value("box_qty", "0")
        if free:
            inv.set_value("free_qty", free)
        added = inv.try_add_to_cart()
        if inv.cart_row_count():
            inv.clear_cart()
        assert not added, f"a TP/VAT line with Box Qty 0 (Free Qty {free}) was added to the cart"

    @pytest.mark.parametrize("text", ["", "-", "abc"])
    @allure.story("Box Qty is required: empty / non-numeric input is blocked")
    @pytest.mark.negative
    def test_box_qty_required(self, tpvat_inventory, text):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.type_value("box_qty", text)
        assert not inv.try_add_to_cart()
        assert any("box qty is required" in e.lower() for e in inv.form_errors()), inv.form_errors()

    @pytest.mark.parametrize("key,text", [("tp_per_box", "-5"), ("vat_per_box", "-5"), ("special_discount", "-5"),
                                          ("box_qty", "-1"), ("free_qty", "-3")])
    @allure.story("Negative numbers cannot be entered: typing '-' + digits leaves 0 in the field")
    @pytest.mark.negative
    def test_negative_input_is_clamped_to_zero(self, tpvat_inventory, key, text):
        inv = tpvat_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        shown = inv.type_value(key, text)
        assert float(shown or 0) >= 0 and shown in ("0", "0.0", ""), f"{key}: typed {text!r} left {shown!r}"

    @allure.story("Past expiry dates are selectable and accepted - intentional (confirmed 2026-10-08)")
    def test_past_expiry_allowed(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        _fill(inv, tp=40, box=1)
        inv.set_expiry_date(1, "Jan", 2026)
        inv.set_value("batch_no", flow.next_batch("T"))
        assert inv.try_add_to_cart(), "an item with a past Expiry Date was rejected"

    @allure.story("Storage 'WHS' has no input (one warehouse per pharmacy); 'Rack' takes a value")
    def test_storage_types(self, tpvat_inventory):
        inv = tpvat_inventory
        inv.select_storage_type("Rack")
        assert inv.field_is_enabled("rack_no")
        inv.select_storage_type("WHS")
        assert not inv.field_is_enabled("rack_no")

    @allure.story("Removing a line frees its product to be added again")
    def test_product_can_be_re_added_after_delete(self, tpvat_inventory, flow):
        inv = tpvat_inventory
        assert _add(inv, flow, tp=89.44, box=2)
        inv.delete_cart_row(inv.cart_row(0))
        assert _add(inv, flow, tp=50, box=1) and inv.total_items() == 1
