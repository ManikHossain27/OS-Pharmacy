"""Opening Stock mode - 'Add Items to Cart' create form (spec sections 14-21, 38, 41, 46).

Everything here exercises ONE screen: the create form (plus the cart row it produces). Nothing is completed, so no
stock / financial data is created.

Facts verified live 2026-10-12 (the oracle is utils.opening_calc):
* Opening Stock (%) defaults to 12 and goes back to 12 when another product is selected;
* BTP+VAT/Box = ROUND(Retail Price/Box x (1 - % / 100), 2); the % is clamped to 0..100;
* editing Retail Price/Box or the % re-derives BTP+VAT/Box; Total BTP + VAT = BTP+VAT/Box x Box Qty;
* editing Total BTP + VAT sets BTP+VAT/Box = Total / Box Qty.
Known defect asserted at its desired behaviour (red until fixed): BUG-INV-030. (BUG-INV-005/006 were closed as accepted behaviour on 2026-10-12.)
"""
from __future__ import annotations

import allure
import pytest

from utils.opening_calc import DEFAULT_PCT, btp_for

pytestmark = [pytest.mark.inventory, pytest.mark.ui]

ALL_FIELDS = ("company", "product", "box_qty", "qty_per_box", "total_qty", "free_qty", "retail_price",
              "wholesale_price", "total_price", "price_per_box", "min_qty", "rack_no", "storage_type", "batch_no",
              "expiry_date", "barcode_value", "special_discount", "opening_stock_percent")


def _set(inv, key: str, value, wait: int = 300) -> None:
    inv.set_value(key, value)
    inv.field(key).blur()
    inv.page.wait_for_timeout(wait)


def _num(inv, key: str) -> float:
    return float((inv.value_of(key) or "0").replace(",", "") or 0)


def _fill(inv, *, retail=None, pct=None, btp=None, box=1, free=None, special=None, product="P0"):
    inv.select_product(inv.resolve_product(product), exact=True)
    if retail is not None:
        _set(inv, "retail_price", retail)
    if pct is not None:
        _set(inv, "opening_stock_percent", pct)
    if btp is not None:
        _set(inv, "price_per_box", btp)
    _set(inv, "box_qty", box)
    if free:
        _set(inv, "free_qty", free)
    if special is not None:
        inv.type_value("special_discount", str(special))


def _add(inv, flow, **kw) -> bool:
    _fill(inv, **kw)
    inv.set_value("batch_no", flow.next_batch("O"))
    return inv.try_add_to_cart()


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - create form")
class TestFormStructure:

    @allure.story("Opening Stock mode opens with every spec field, the Opening Stock (%) and Special Discount (Tk) (spec 14, 16)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_all_fields_present(self, opening_inventory):
        inv = opening_inventory
        missing = [k for k in ALL_FIELDS if inv.field(k).count() == 0]
        assert not missing, f"Opening Stock form is missing {missing}"

    @allure.story("Opening Stock mode has no TP/Box or VAT/Box input (those belong to TP/VAT mode)")
    def test_no_tpvat_fields(self, opening_inventory):
        page = opening_inventory.page
        assert page.locator("#tpPerBox").count() == 0 and page.locator("#vatPerBox").count() == 0

    @allure.story("Spec 15: Opening Stock (%) is populated automatically with 12 when the mode is selected")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_default_percentage_is_12(self, opening_inventory):
        assert float(opening_inventory.value_of("opening_stock_percent")) == DEFAULT_PCT

    @allure.story("Required markers: Product, Box Qty, Qty/Box, Total Qty, Retail Price/Box, BTP+VAT/Box (spec 46)")
    def test_required_markers(self, opening_inventory):
        page = opening_inventory.page
        required = {t.strip() for t in page.locator(".ant-form-item-required").all_inner_texts()}
        for label in ("Product", "Box Qty", "Qty/Box", "Total Qty", "Retail Price/Box", "BTP+VAT/Box"):
            assert label in required, f"{label!r} should be marked required; got {sorted(required)}"
        assert "Opening Stock (%)" not in required and "Wholesale Price/Box" not in required

    @allure.story("Submit button reads 'Add Items to Cart'")
    def test_submit_button_label(self, opening_inventory):
        assert opening_inventory.submit_button().inner_text().strip() == "Add Items to Cart"


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - create form")
class TestBtpDerivation:
    """BTP+VAT/Box = Retail Price/Box x (1 - Opening Stock % / 100) (spec 16, 18, 20; sheet col I)."""

    @allure.story("Spec 16: selecting a product preloads Qty/Box, Retail and Wholesale and derives BTP+VAT/Box at once")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_product_preloads_and_derives(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.page.wait_for_timeout(600)
        retail = _num(inv, "retail_price")
        assert retail > 0 and _num(inv, "qty_per_box") > 0 and _num(inv, "wholesale_price") > 0, inv.form_snapshot()
        assert _num(inv, "opening_stock_percent") == DEFAULT_PCT
        assert _num(inv, "price_per_box") == pytest.approx(btp_for(retail, DEFAULT_PCT), abs=0.0051)

    @pytest.mark.parametrize("retail", [100, 33.33, 0.5, 999.99, 612, 125.75])
    @allure.story("Retail Price/Box edit re-derives BTP+VAT/Box at the current % while it is system-calculated (spec 20)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_retail_edit_rederives_btp(self, opening_inventory, retail):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", retail)
        assert _num(inv, "price_per_box") == pytest.approx(btp_for(retail, 12), abs=0.0051)

    @pytest.mark.parametrize("pct", [0, 1, 7.5, 12.345, 20, 33.333, 50, 99, 100])
    @allure.story("Opening Stock (%) edit re-derives BTP+VAT/Box = Retail x (1 - %) (spec 15, 18)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_percentage_edit_rederives_btp(self, opening_inventory, pct):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 250)
        _set(inv, "opening_stock_percent", pct)
        assert _num(inv, "price_per_box") == pytest.approx(btp_for(250, pct), abs=0.0051), \
            f"retail 250 at {pct} % should give {btp_for(250, pct)}, form shows {inv.value_of('price_per_box')}"

    @pytest.mark.parametrize("typed,clamped", [(-5, 0), (150, 100), (1000, 100)])
    @allure.story("Out-of-range Opening Stock % is clamped to 0..100 and BTP+VAT/Box follows the clamped value")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.negative
    def test_percentage_is_clamped(self, opening_inventory, typed, clamped):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        shown = inv.type_value("opening_stock_percent", str(typed))
        assert float(shown or 0) == clamped, f"typed {typed} -> field shows {shown!r}, expected {clamped}"
        assert _num(inv, "price_per_box") == pytest.approx(btp_for(100, clamped), abs=0.0051)

    @allure.story("BTP+VAT/Box is rounded to 2 decimals (33.33 at 12 % -> 29.33, not 29.3304)")
    def test_two_decimal_rounding(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 33.33)
        shown = inv.value_of("price_per_box")
        assert shown == "29.33", f"BTP+VAT/Box shows {shown!r}, expected 29.33"

    @allure.story("Selecting another product resets the Opening Stock % to the default 12 (spec 15)")
    def test_product_change_resets_percentage(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "opening_stock_percent", 30)
        inv.select_product(inv.resolve_product("P1"), exact=True)
        inv.page.wait_for_timeout(500)
        assert float(inv.value_of("opening_stock_percent")) == DEFAULT_PCT
        assert _num(inv, "price_per_box") == pytest.approx(btp_for(_num(inv, "retail_price"), 12), abs=0.0051)

    @allure.story("Retail Price/Box 0 gives BTP+VAT/Box 0")
    def test_retail_zero_gives_zero_btp(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 0)
        assert _num(inv, "price_per_box") == 0


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - create form")
class TestTotalsAndQuantities:

    @pytest.mark.parametrize("box,qpb_total", [(1, 1), (5, 5), (10, 10), (2.5, 2.5)])
    @allure.story("Spec 17: Total Qty = Box Qty x Qty/Box")
    def test_total_qty(self, opening_inventory, box, qpb_total):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        qpb = _num(inv, "qty_per_box")
        _set(inv, "box_qty", box)
        assert _num(inv, "total_qty") == pytest.approx(box * qpb)

    @allure.story("Total Qty edit updates Box Qty (35 pcs of a 10-per-box product -> 3.5 boxes)")
    def test_total_qty_drives_box_qty(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        qpb = _num(inv, "qty_per_box")
        _set(inv, "total_qty", qpb * 3.5)
        assert _num(inv, "box_qty") == pytest.approx(3.5)

    @allure.story("Spec 18: Total BTP + VAT = BTP+VAT/Box x Box Qty (retail 100 -> 88 x 10 = 880)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_total_is_btp_times_box(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "box_qty", 10)
        assert _num(inv, "price_per_box") == 88 and _num(inv, "total_price") == pytest.approx(880)

    @allure.story("Total BTP + VAT edit sets BTP+VAT/Box = Total / Box Qty (500 / 10 = 50)")
    def test_total_edit_sets_btp_per_box(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "box_qty", 10)
        _set(inv, "total_price", 500)
        assert _num(inv, "price_per_box") == pytest.approx(50)

    @allure.story("Box Qty change after the derived BTP keeps BTP+VAT/Box and updates the total")
    def test_box_qty_change_updates_total(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "box_qty", 4)
        _set(inv, "box_qty", 7)
        assert _num(inv, "price_per_box") == 88 and _num(inv, "total_price") == pytest.approx(616)


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - manual BTP+VAT/Box override")
class TestManualOverride:
    """Spec 19: the user may overwrite BTP+VAT/Box; the Total uses the manual value, the Opening Stock % is
    back-calculated from it, and a later Retail edit must not discard the override (spec 20)."""

    @allure.story("Spec 19: manual BTP+VAT/Box 80 x Box Qty 10 -> Total Tk 800")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_manual_btp_drives_total(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "box_qty", 10)
        _set(inv, "price_per_box", 80)
        assert _num(inv, "total_price") == pytest.approx(800)

    @allure.story("Spec 19: a Box Qty change after a manual BTP keeps the manual BTP and recalculates the Total")
    @pytest.mark.regression
    def test_box_qty_after_manual_btp(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "price_per_box", 70)
        _set(inv, "box_qty", 3)
        assert _num(inv, "price_per_box") == 70 and _num(inv, "total_price") == pytest.approx(210)

    @allure.story("Accepted behaviour (product owner, 2026-10-12): a manual BTP+VAT/Box does NOT back-calculate the Opening Stock %")
    @pytest.mark.regression
    def test_manual_btp_leaves_percentage_unchanged(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "box_qty", 10)
        before = float(inv.value_of("opening_stock_percent") or 0)
        _set(inv, "price_per_box", 70)
        assert float(inv.value_of("opening_stock_percent") or 0) == before
        assert _num(inv, "price_per_box") == 70 and _num(inv, "total_price") == pytest.approx(700)

    @allure.story("Accepted behaviour (product owner, 2026-10-12): editing Retail after a manual BTP re-derives BTP at the current %")
    @pytest.mark.regression
    def test_retail_edit_rederives_btp(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "box_qty", 10)
        _set(inv, "price_per_box", 70)
        _set(inv, "retail_price", 150)
        pct = float(inv.value_of("opening_stock_percent") or 0)
        assert _num(inv, "price_per_box") == pytest.approx(btp_for(150, pct), abs=0.0051)

    @allure.story("Editing the Opening Stock % after a manual BTP re-derives BTP from the retail price (the % is the explicit instruction)")
    def test_percentage_edit_after_manual_btp_rederives(self, opening_inventory):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        _set(inv, "retail_price", 100)
        _set(inv, "price_per_box", 70)
        _set(inv, "opening_stock_percent", 25)
        assert _num(inv, "price_per_box") == 75


@allure.epic("Inventory")
@allure.feature("Opening Stock mode - create form")
class TestAddToCart:

    @allure.story("Cart row = derived BTP+VAT/Box and Total Price = BTP+VAT/Box x Box Qty (retail 100, 12 %, 2 boxes -> 88 / 176)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_total_price_formula(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=100, box=2)
        row = inv.cart_rows()[0]
        assert "88.00" in row["BTP+VAT/Box"] and "176.00" in row["Total Price"]
        assert inv.cart_total_price() == pytest.approx(176.0)

    @allure.story("A non-default Opening Stock % is used for the cart line (retail 200 at 25 % -> 150)")
    @pytest.mark.regression
    def test_custom_percentage_in_cart(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=200, pct=25, box=3)
        row = inv.cart_rows()[0]
        assert "150.00" in row["BTP+VAT/Box"] and "450.00" in row["Total Price"]

    @allure.story("A manual BTP+VAT/Box is what the cart shows and totals")
    @pytest.mark.regression
    def test_manual_btp_in_cart(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=100, btp=80, box=10)
        row = inv.cart_rows()[0]
        assert "80.00" in row["BTP+VAT/Box"] and "800.00" in row["Total Price"]

    @allure.story("Free pieces do not add cost: Total Price = BTP+VAT/Box x Box Qty only (no VAT-on-free in this mode)")
    @pytest.mark.regression
    def test_free_qty_does_not_change_total(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=100, box=2, free=7)
        row = inv.cart_rows()[0]
        assert "176.00" in row["Total Price"] and row["Free"].strip() == "7"

    @allure.story("Special Discount (Tk) is accepted and shown in the cart as 'Tk 20.00 / SP.Dis / % of the line total'")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_special_discount_in_cart(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=100, box=2, special=20)       # line total 176 -> 20 is 11.36 %
        cell = inv.cart_rows()[0]["Discount"]
        assert "SP.Dis" in cell and "20.00" in cell, cell

    @allure.story("Business rule: a product can be in the cart ONCE - a second add is refused with a message")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_same_product_cannot_be_added_twice(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=100, box=2)
        _fill(inv, retail=50, box=5)
        inv.set_value("batch_no", flow.next_batch("O"))
        assert not inv.try_add_to_cart() and inv.total_items() == 1
        assert any("already in the cart" in m.lower() for m in inv.messages()), inv.messages()

    @pytest.mark.parametrize("free", [0, 5])
    @allure.story("Box Qty must be greater than 0 (confirmed 2026-10-08; same rule in every mode)")
    @allure.issue("BUG-INV-030")
    @pytest.mark.negative
    def test_box_qty_must_be_greater_than_zero(self, opening_inventory, free):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.type_value("box_qty", "0")
        if free:
            inv.set_value("free_qty", free)
        added = inv.try_add_to_cart()
        if inv.cart_row_count():
            inv.clear_cart()
        assert not added, f"an Opening Stock line with Box Qty 0 (Free Qty {free}) was added to the cart"

    @pytest.mark.parametrize("text", ["", "-", "abc"])
    @allure.story("Box Qty is required: empty / non-numeric input is blocked with 'Box Qty is required'")
    @pytest.mark.negative
    def test_box_qty_required(self, opening_inventory, text):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.type_value("box_qty", text)
        assert not inv.try_add_to_cart()
        assert any("box qty is required" in e.lower() for e in inv.form_errors()), inv.form_errors()

    @pytest.mark.parametrize("key,text", [("retail_price", "-5"), ("price_per_box", "-5"), ("special_discount", "-5"),
                                          ("box_qty", "-1"), ("free_qty", "-3")])
    @allure.story("Negative numbers cannot be entered: typing '-' + digits leaves 0 in the field")
    @pytest.mark.negative
    def test_negative_input_is_clamped_to_zero(self, opening_inventory, key, text):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        shown = inv.type_value(key, text)
        assert float(shown or 0) >= 0 and shown in ("0", "0.0", ""), f"{key}: typed {text!r} left {shown!r}"

    @allure.story("Retail Price/Box is required: clearing it blocks the add")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_retail_price_required(self, opening_inventory, flow):
        inv = opening_inventory
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.type_value("retail_price", "")
        _set(inv, "box_qty", 1)
        inv.set_value("batch_no", flow.next_batch("O"))
        added = inv.try_add_to_cart()
        if inv.cart_row_count():
            inv.clear_cart()
        assert not added, "an Opening Stock line without a Retail Price/Box was added (the field is required)"

    @allure.story("Past expiry dates are selectable and accepted - intentional (confirmed 2026-10-08)")
    def test_past_expiry_allowed(self, opening_inventory, flow):
        inv = opening_inventory
        _fill(inv, retail=40, box=1)
        inv.set_expiry_date(1, "Jan", 2026)
        inv.set_value("batch_no", flow.next_batch("O"))
        assert inv.try_add_to_cart(), "an item with a past Expiry Date was rejected"

    @allure.story("Storage 'WHS' has no input (one warehouse per pharmacy); 'Rack' takes a value")
    def test_storage_types(self, opening_inventory):
        inv = opening_inventory
        inv.select_storage_type("Rack")
        assert inv.field_is_enabled("rack_no")
        inv.select_storage_type("WHS")
        assert not inv.field_is_enabled("rack_no")

    @allure.story("Removing a line frees its product to be added again")
    def test_product_can_be_re_added_after_delete(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=100, box=2)
        inv.delete_cart_row(inv.cart_row(0))
        assert _add(inv, flow, retail=50, box=1) and inv.total_items() == 1

    @allure.story("Mode switch keeps modes apart: Opening Stock cart is separate from the Default cart")
    def test_cart_is_per_mode(self, opening_inventory, flow):
        inv = opening_inventory
        assert _add(inv, flow, retail=100, box=2) and inv.total_items() == 1
        inv.switch_mode("Default")
        assert inv.total_items() == 0, "an Opening Stock line leaked into the Default cart"
        inv.switch_mode("Opening Stock")
        assert inv.total_items() == 1, "the Opening Stock cart was lost after switching modes"
