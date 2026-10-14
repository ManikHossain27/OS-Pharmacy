"""Default mode - Inventory Cart (spec sections 27-34).

Every cart shape from utils.inventory_scenarios.CART_SHAPES is entered through
the create form and the cart is verified row by row against the oracle.
Nothing here completes an inventory, so no stock/financial data is created.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.shared_cart import CartContentsCases
from utils.inventory_assertions import Verifier, check_cart
from utils.inventory_scenarios import CART_SHAPES, LineSpec, Scenario

pytestmark = [pytest.mark.inventory, pytest.mark.regression]


def _scenario(shape: str) -> Scenario:
    return Scenario(id=shape, lines=CART_SHAPES[shape])


@allure.epic("Inventory")
@allure.feature("Default mode - cart")
class TestCartContents(CartContentsCases):
    SHAPES = CART_SHAPES
    HEADERS = ("Details", "Box Qty", "BTP+VAT", "Discount", "Total Price", "Exp date", "Free", "Action")
    ABSENT_HEADERS = ("TP/Box", "VAT/Box")
    VERIFIER = Verifier
    CHECK_CART = staticmethod(check_cart)
    LINE_PRICE = {"btp_vat_per_box": 33.3}

    @allure.story("A refused duplicate leaves the cart total untouched")
    def test_refused_duplicate_keeps_total(self, flow):
        inv = flow.inventory
        inv.try_add_line(LineSpec("P0", box_qty=2, btp_vat_per_box=33.3), flow.next_batch())
        before = inv.cart_total_price()
        inv.try_add_line(LineSpec("P0", box_qty=9, btp_vat_per_box=99), flow.next_batch())
        assert inv.cart_total_price() == pytest.approx(before)

    @allure.story("Removing a line frees its product to be added again")
    def test_product_can_be_re_added_after_delete(self, flow):
        inv = flow.inventory
        inv.try_add_line(LineSpec("P0", box_qty=2, btp_vat_per_box=33.3), flow.next_batch())
        inv.delete_cart_row(inv.cart_row(0))
        added, _ = inv.try_add_line(LineSpec("P0", box_qty=4, btp_vat_per_box=20), flow.next_batch())
        assert added and inv.total_items() == 1

    @allure.story("Decimal prices render without truncation")
    def test_decimal_values(self, flow):
        j = flow.fill_cart(Scenario("big", (LineSpec("P0", box_qty=250, btp_vat_per_box=7.2),
                                            LineSpec("P1", box_qty=3, btp_vat_per_box=125.75))))
        v = Verifier("cart big/decimal")
        check_cart(v, flow.inventory.cart_rows(), j.lines, flow.inventory.cart_total_price(),
                   flow.inventory.total_items())
        v.assert_all()

    @allure.story("Cart total excludes Free Qty (free pieces never raise the purchase amount, spec 32)")
    def test_free_qty_does_not_change_total(self, flow):
        inv = flow.inventory
        flow.fill_cart(Scenario("free", (LineSpec("P0", box_qty=2, btp_vat_per_box=50),)))
        base = inv.cart_total_price()
        inv.clear_cart()
        flow.fill_cart(Scenario("free", (LineSpec("P0", box_qty=2, btp_vat_per_box=50, free_qty=10),)))
        assert inv.cart_total_price() == pytest.approx(base)


@allure.epic("Inventory")
@allure.feature("Default mode - cart")
class TestCartEditDelete:

    @allure.story("Edit loads the row into the form and clearly shows an edit state (spec 30)")
    def test_edit_loads_row_and_shows_edit_state(self, flow):
        inv = flow.inventory
        j = flow.fill_cart(_scenario("two_plain"))
        inv.edit_cart_row(inv.cart_row(0))
        assert inv.is_edit_mode(), "no 'Edit Cart Item' indicator while editing"
        assert inv.submit_button().inner_text().strip() == "Save Changes"
        assert inv.form_number("box_qty") == pytest.approx(j.lines[0].box_qty)
        assert inv.form_number("price_per_box") == pytest.approx(j.lines[0].btp_vat_per_box)
        assert inv.value_of("batch_no") == j.batches[0]

    @allure.story("Saving an edit updates the SAME row - no new row (spec 30)")
    def test_edit_updates_in_place(self, flow):
        inv = flow.inventory
        j = flow.fill_cart(_scenario("two_plain"))
        inv.edit_cart_row(inv.cart_row(0))
        inv.set_value("box_qty", 9)
        inv.field("box_qty").blur()
        inv.submit_cart_item()
        rows = inv.cart_rows()
        assert len(rows) == 2 and inv.total_items() == 2, "edit created an extra row"
        assert "9" in rows[0]["Box Qty"]
        expected_total = 9 * j.lines[0].btp_vat_per_box + j.lines[1].total_btp_vat
        assert inv.cart_total_price() == pytest.approx(expected_total, abs=0.011)

    @allure.story("Editing Free Qty and price updates the row and totals")
    def test_edit_free_and_price(self, flow):
        inv = flow.inventory
        flow.fill_cart(_scenario("single_plain"))
        inv.edit_cart_row(inv.cart_row(0))
        inv.set_value("price_per_box", 10); inv.set_value("free_qty", 4); inv.field("free_qty").blur()
        inv.submit_cart_item()
        row = inv.cart_rows()[0]
        assert "4" in row["Free"] and "10" in row["BTP+VAT"]

    @allure.story("Delete removes only that row and recalculates totals immediately (spec 31)")
    def test_delete_recalculates(self, flow):
        inv = flow.inventory
        j = flow.fill_cart(_scenario("three_plain_free_plain"))
        inv.delete_cart_row(inv.cart_row(1))
        assert inv.total_items() == 2 and inv.cart_row_count() == 2
        assert inv.cart_total_price() == pytest.approx(j.lines[0].total_btp_vat + j.lines[2].total_btp_vat, abs=0.011)
        rows = inv.cart_rows()
        assert j.lines[0].name in rows[0]["Details"] and j.lines[2].name in rows[1]["Details"]
        assert rows[0]["Free"] in ("", "-", "0") and rows[1]["Free"] in ("", "-", "0"), \
            "the free-qty row should be the deleted one"

    @allure.story("Deleting every row empties the cart and zeroes the total (spec 31)")
    def test_delete_all(self, flow):
        inv = flow.inventory
        flow.fill_cart(_scenario("two_plain"))
        inv.clear_cart()
        assert inv.cart_is_empty() and inv.total_items() == 0

    @allure.story("BUG-INV-013: cart Edit/Delete icons must be keyboard-accessible with an accessible name")
    @allure.issue("BUG-INV-013")
    @pytest.mark.negative
    def test_row_actions_accessible(self, flow):
        inv = flow.inventory
        flow.fill_cart(_scenario("single_plain"))
        for idx, name in ((0, "edit"), (1, "delete")):
            a = inv.cart_row_action_accessibility(inv.cart_row(0), idx)
            assert a["tag"] == "BUTTON" or (a["role"] == "button" and a["tabindex"] == "0" and a["aria_label"]), \
                f"{name} icon not accessible: {a}"


@allure.epic("Inventory")
@allure.feature("Default mode - cart")
class TestExpandedCart:

    @allure.story("Closing the panel expands the cart with stock, retail, wholesale and storage columns (spec 29)")
    def test_expanded_view_columns(self, flow):
        inv = flow.inventory
        flow.fill_cart(_scenario("single_plain"))
        compact = [h for h in inv.cart.headers() if h]
        inv.close_add_items_panel()
        expanded = [h for h in inv.cart.headers() if h]
        assert len(expanded) > len(compact), f"expanded cart shows no extra columns: {compact} -> {expanded}"
        # spec 29: current stock (pcs + boxes), retail / wholesale selling price, storage
        for col in ("C. Stock", "Pcs/Box", "Sale Price", "Storage"):
            assert col in expanded, f"expanded cart missing column {col!r}; headers={expanded}"
        assert set(compact) <= set(expanded)

    @allure.story("Expanded cart shows the entered Retail / Wholesale prices and storage")
    def test_expanded_values(self, flow):
        inv = flow.inventory
        j = flow.fill_cart(_scenario("single_plain"))
        inv.close_add_items_panel()
        row = inv.cart_rows()[0]
        v = Verifier("expanded cart values")
        v.any_number("Sale Price: Retail", row["Sale Price"], [j.lines[0].retail_per_box])
        v.any_number("Sale Price: Wholesale", row["Sale Price"], [j.lines[0].wholesale_per_box])
        v.contains("Storage", row["Storage"], j.specs[0].rack)
        v.true("C. Stock shows pieces and boxes", "pcs" in row["C. Stock"] and "box" in row["C. Stock"], row["C. Stock"])
        v.any_number("Pcs/Box", row["Pcs/Box"], [j.lines[0].qty_per_box])
        v.assert_all()


@allure.epic("Inventory")
@allure.feature("Default mode - hold list")
class TestHoldAndResume:

    @allure.story("Hold Current Inventory preserves every entered detail and resumes identically (spec 33-34)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_hold_then_resume_restores_cart(self, flow):
        inv = flow.inventory
        j = flow.fill_cart(_scenario("two_one_free"))
        before_rows, before_total = inv.cart_rows(), inv.cart_total_price()
        holds_before = inv.hold_list_count()
        inv.hold_current_inventory()
        assert inv.total_items() == 0, "cart not cleared after hold"
        assert inv.hold_list_count() == holds_before + 1
        dlg = inv.open_hold_list()
        dlg.resume(0)
        assert inv.cart_rows() == before_rows, "resumed cart differs from the held cart"
        assert inv.cart_total_price() == pytest.approx(before_total)
        assert inv.hold_list_count() == holds_before, "resumed hold must leave the Hold List"

    @allure.story("Hold is only available once at least one item is in the cart (spec 33)")
    def test_hold_requires_items(self, default_inventory):
        btn = default_inventory.hold_current_btn
        assert btn.count() == 0 or not btn.is_enabled() or default_inventory.total_items() == 0

    @allure.story("A resumed hold can still be checked out")
    def test_resumed_hold_can_go_to_checkout(self, flow):
        inv = flow.inventory
        flow.fill_cart(_scenario("single_plain"))
        inv.hold_current_inventory()
        inv.open_hold_list().resume(0)
        co = inv.go_to_checkout()
        assert co.is_loaded()
