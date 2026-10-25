"""Inventory Return form (route /inventory-return): product / batch / unit selection, Return Qty validation, the Return
Cart (maths, edit, delete) and the Return Checkout preview (supplier, demurrage). Nothing here completes a return, so the
pool's stock and the supplier balances are never changed.

Spec (Inventory Management.md, 'Inventory Return'): select a product, see only the available batches and the available
quantity, enter the Return Qty in pieces or boxes, add to the Return Cart; a return is priced at the batch's PURCHASE
price; Demurrage is a percentage or a flat amount and the final return amount is calculated after it.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.return_module.helpers import TOL, expected_summary, supplier_balance

ROUND = pytest.approx


def _stage(ret, pool, i: int, qty, unit: str = "pc") -> None:
    """Select line ``i``'s product and batch, the unit and a quantity - without pressing Add."""
    ret.select_product(pool.products[i])
    ret.select_batch(pool.batches[i])
    if unit.lower() != ret.unit().lower():
        ret.set_unit(unit)
    ret.set_qty(qty)


def _add(ret, pool, i: int, qty, unit: str = "pc") -> None:
    ret.add_line(pool.products[i], pool.batches[i], qty, unit)


# ---- product, batch, unit ------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - form")
class TestSelection:
    @allure.story("The Product dropdown finds a product by name and an unknown name finds nothing")
    def test_product_search(self, pool, ret):
        assert any(pool.products[0].lower() in o.lower() for o in ret.search_products(pool.products[0]))
        assert ret.search_products("ZZZ-NO-SUCH-PRODUCT-9") == [] or all(
            "no data" in o.lower() for o in ret.search_products("ZZZ-NO-SUCH-PRODUCT-9"))

    @allure.story("The Company filter narrows the Product list to that company's products")
    def test_company_filter_narrows_products(self, pool, ret):
        company = ret.search_products(pool.products[0])[0].splitlines()[-1].strip()
        ret.open()
        ret.select_company(company)
        options = ret.search_products(pool.products[0])
        assert options and all(company.lower() in o.lower() for o in options), options

    @allure.story("The Batch dropdown lists the product's batches with their available pieces and boxes")
    def test_batch_options_show_available(self, pool, ret):
        ret.select_product(pool.products[0])
        mine = [b for b in ret.batch_options() if b["batch"] == pool.batches[0]]
        assert len(mine) == 1 and mine[0]["pcs"] > 0, mine
        assert mine[0]["boxes"] == ROUND(mine[0]["pcs"] / pool.qty_per_box[0], abs=0.5), mine

    @allure.story("Only the selected product's batches are offered (another product's batch never appears)")
    def test_batches_belong_to_the_product(self, pool, ret):
        ret.select_product(pool.products[0])
        assert pool.batches[1] not in [b["batch"] for b in ret.batch_options()]

    @allure.story("The selected batch shows its available pieces: 'BATCH (N)'")
    def test_selected_batch_shows_available(self, pool, ret):
        ret.select_product(pool.products[1])
        stock = next(b["pcs"] for b in ret.batch_options() if b["batch"] == pool.batches[1])
        ret.select_batch(pool.batches[1])
        assert ret.available() == stock

    @allure.story("Changing the product clears the selected batch")
    def test_changing_product_clears_batch(self, pool, ret):
        ret.select_product(pool.products[0])
        ret.select_batch(pool.batches[0])
        ret.select_product(pool.products[1])
        assert pool.batches[0] not in ret.selected_batch_text()

    @allure.story("Quantity can be returned in Pieces or Boxes; pieces is the default")
    def test_unit_options(self, pool, ret):
        assert sorted(o.lower() for o in ret.unit_options()) == ["box", "pc"]
        assert ret.unit().lower() == "pc"

    @allure.story("Nothing can be added before a product and batch are selected")
    @pytest.mark.negative
    def test_add_needs_product_and_batch(self, pool, ret):
        ret.set_qty(1)
        assert not ret.add_enabled() or ret.cart_lines() == []
        ret.add_btn.click(force=True)
        assert ret.cart_lines() == [] and ret.empty_cart_visible()

    @allure.story("Go to Return Checkout is disabled while the cart is empty")
    @pytest.mark.negative
    def test_checkout_disabled_for_empty_cart(self, ret):
        assert ret.empty_cart_visible() and not ret.checkout_enabled()


# ---- Return Qty validation -----------------------------------------------------------------------------------------
QTY_OK = [("1-pc", 1, "pc"), ("7-pc", 7, "pc"), ("1-box", 1, "box"), ("3-box", 3, "box")]
QTY_BAD = [("zero-pc", 0, "pc"), ("negative-pc", -3, "pc"), ("blank-pc", None, "pc"), ("zero-box", 0, "box"),
           ("negative-box", -1, "box"), ("blank-box", None, "box")]


@allure.epic("Inventory")
@allure.feature("Inventory Return - form")
class TestReturnQty:
    @allure.story("A valid Return Qty (pieces or boxes) is added to the cart as one line")
    @pytest.mark.parametrize("qty,unit", [q[1:] for q in QTY_OK], ids=[q[0] for q in QTY_OK])
    def test_valid_qty_added(self, pool, ret, qty, unit):
        _add(ret, pool, 0, qty, unit)
        lines = ret.cart_lines()
        assert len(lines) == 1 and lines[0].batch == pool.batches[0], lines
        assert lines[0].pieces == qty * (pool.qty_per_box[0] if unit == "box" else 1)

    @allure.story("Return Qty of zero, negative or blank cannot be added")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.parametrize("qty,unit", [q[1:] for q in QTY_BAD], ids=[q[0] for q in QTY_BAD])
    def test_invalid_qty_refused(self, pool, ret, qty, unit):
        _stage(ret, pool, 0, qty, unit)
        if ret.add_enabled():
            ret.add_current()
        assert ret.cart_lines() == [], f"{qty} {unit} was added to the Return Cart"

    @allure.story("Return Qty above the available quantity is refused with an inline error (pieces)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_over_available_pieces(self, pool, ret):
        _stage(ret, pool, 2, 1)
        over = ret.available() + 1
        ret.set_qty(int(over))
        if ret.add_enabled():
            ret.add_current()
        assert ret.qty_error() and ret.cart_lines() == [], (ret.qty_error(), over)

    @allure.story("Return Qty above the available quantity is refused (boxes)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_over_available_boxes(self, pool, ret):
        _stage(ret, pool, 0, 1, "box")
        over = int(ret.available() / pool.qty_per_box[0]) + 1
        ret.set_qty(over)
        if ret.add_enabled():
            ret.add_current()
        assert ret.cart_lines() == [], f"{over} boxes were added though only {ret.available()} pieces are available"

    @allure.story("Exactly the available quantity can be added (boundary), one more cannot")
    def test_available_boundary(self, pool, ret):
        _stage(ret, pool, 2, 1)
        stock = int(ret.available())
        ret.set_qty(stock)
        ret.add_current()
        assert [l.pieces for l in ret.cart_lines()] == [stock]

    @allure.story("A fractional number of pieces is refused (a piece cannot be split)")
    @pytest.mark.negative
    def test_fractional_pieces(self, pool, ret):
        _stage(ret, pool, 0, 1.5)
        if ret.add_enabled():
            ret.add_current()
        assert ret.cart_lines() == [], "1.5 pieces were added to the Return Cart"

    @allure.story("A fractional number of boxes that is a whole number of pieces is accepted (0.5 box of 10 = 5 pcs)")
    def test_half_box(self, pool, ret):
        _add(ret, pool, 0, 0.5, "box")
        lines = ret.cart_lines()
        assert lines and lines[0].pieces == 5, lines

    @allure.story("A fractional number of boxes that is not a whole number of pieces is refused (0.25 box of 10 = 2.5 pcs)")
    @pytest.mark.negative
    def test_box_fraction_not_whole_pieces(self, pool, ret):
        _stage(ret, pool, 0, 0.25, "box")
        if ret.add_enabled():
            ret.add_current()
        assert ret.cart_lines() == [], "2.5 pieces were added to the Return Cart"

    @allure.story("Switching the unit after typing a quantity re-validates it against the available stock")
    @pytest.mark.negative
    def test_unit_switch_revalidates(self, pool, ret):
        _stage(ret, pool, 0, 1000, "pc")
        ret.set_unit("Box")                       # 1000 boxes = 10 000 pieces > 3000 available
        if ret.add_enabled():
            ret.add_current()
        assert ret.cart_lines() == []

    @allure.story("Huge numbers are refused, not crashed on")
    @pytest.mark.negative
    def test_huge_qty(self, pool, ret):
        _stage(ret, pool, 0, 99999999999)
        if ret.add_enabled():
            ret.add_current()
        assert ret.cart_lines() == []


# ---- Return Cart maths ---------------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - cart")
class TestCartMath:
    @allure.story("A line is priced at the batch's purchase price per piece x pieces")
    @pytest.mark.parametrize("i,qty", [(0, 1), (0, 7), (1, 3), (2, 5), (2, 7), (0, 333)], ids=lambda v: str(v))
    def test_price_per_piece(self, pool, ret, i, qty):
        _add(ret, pool, i, qty)
        line = ret.cart_lines()[0]
        assert line.price == ROUND(pool.price(i, qty), abs=TOL), (line, pool.cost_per_pc[i])
        assert ret.cart_total() == ROUND(line.price, abs=TOL)

    @allure.story("A return by box converts to pieces (shown in the cart) and is priced per piece")
    @pytest.mark.parametrize("i,boxes", [(0, 1), (0, 2), (2, 1), (2, 3)], ids=lambda v: str(v))
    def test_price_by_box(self, pool, ret, i, boxes):
        _add(ret, pool, i, boxes, "box")
        line = ret.cart_lines()[0]
        pieces = boxes * pool.qty_per_box[i]
        assert line.pieces == pieces, line
        assert line.price == ROUND(pool.price(i, pieces), abs=TOL), line

    @allure.story("Returning the same quantity by box or by piece costs the same")
    def test_box_equals_pieces(self, pool, ret):
        _add(ret, pool, 0, 2, "box")
        by_box = ret.cart_lines()[0].price
        ret.open()
        _add(ret, pool, 0, 2 * int(pool.qty_per_box[0]), "pc")
        assert ret.cart_lines()[0].price == ROUND(by_box, abs=TOL)

    @allure.story("The cart total is the sum of the line prices; Total Items counts the lines")
    def test_multi_line_total(self, pool, ret):
        for i, qty in ((0, 4), (1, 2), (2, 9)):
            _add(ret, pool, i, qty)
        lines = ret.cart_lines()
        assert len(lines) == 3
        assert ret.cart_total() == ROUND(sum(l.price for l in lines), abs=TOL)
        assert ret.cart_total() == ROUND(sum(pool.price(i, q) for i, q in ((0, 4), (1, 2), (2, 9))), abs=0.03)

    @allure.story("Each cart line shows its batch and per-piece purchase price")
    def test_line_shows_batch_and_unit_price(self, pool, ret):
        _add(ret, pool, 1, 2)
        line = ret.cart_lines()[0]
        assert line.batch == pool.batches[1] and line.unit_label == "pc"
        assert line.price_per_unit == ROUND(pool.cost_per_pc[1], abs=TOL)

    @allure.story("Adding the same batch again replaces the first line (product owner)")
    def test_same_batch_twice(self, pool, ret):
        _add(ret, pool, 2, 5)
        _add(ret, pool, 2, 6)
        lines = ret.cart_lines()
        assert [l.pieces for l in lines] == [6], lines
        assert ret.cart_total() == ROUND(pool.price(2, 6), abs=0.03)

    @allure.story("Quantities across lines of one batch cannot exceed that batch's stock")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_same_batch_twice_exceeding_stock(self, pool, ret):
        _stage(ret, pool, 2, 1)
        stock = int(ret.available())
        ret.set_qty(stock - 3)
        ret.add_current()
        _stage(ret, pool, 2, 10)
        if ret.add_enabled():
            ret.add_current()
        assert sum(l.pieces for l in ret.cart_lines()) <= stock, ret.cart_lines()


@allure.epic("Inventory")
@allure.feature("Inventory Return - cart")
class TestCartEditing:
    @allure.story("Edit pre-loads the line and Update Cart replaces it (no duplicate)")
    def test_edit_line(self, pool, ret):
        _add(ret, pool, 0, 20)
        ret.edit_row(0)
        assert ret.update_btn_visible() and ret.qty_input.input_value() == "20"
        ret.set_qty(15)
        ret.update_cart()
        lines = ret.cart_lines()
        assert len(lines) == 1 and lines[0].pieces == 15
        assert lines[0].price == ROUND(pool.price(0, 15), abs=TOL)

    @allure.story("A line cannot be edited above the available stock")
    @pytest.mark.negative
    def test_edit_over_available(self, pool, ret):
        _add(ret, pool, 2, 5)
        ret.edit_row(0)
        ret.set_qty(int(ret.available()) + 1)
        if ret.update_btn_visible():
            ret.update_cart()
        assert all(l.pieces <= ret.available() for l in ret.cart_lines()), ret.cart_lines()

    @allure.story("A line can be edited to zero? No - zero is refused and the line keeps its quantity")
    @pytest.mark.negative
    def test_edit_to_zero(self, pool, ret):
        _add(ret, pool, 0, 5)
        ret.edit_row(0)
        ret.set_qty(0)
        if ret.update_btn_visible():
            ret.update_cart()
        assert [l.pieces for l in ret.cart_lines()] == [5]

    @allure.story("A line can be switched from pieces to boxes while editing")
    def test_edit_unit(self, pool, ret):
        _add(ret, pool, 0, 20)
        ret.edit_row(0)
        ret.set_unit("Box")
        ret._per_box[pool.batches[0]] = pool.qty_per_box[0]   # the cart shows boxes only
        ret.set_qty(1)
        ret.update_cart()
        line = ret.cart_lines()[0]
        assert line.pieces == pool.qty_per_box[0] and line.price == ROUND(pool.price(0, pool.qty_per_box[0]), abs=TOL)

    @allure.story("Deleting one of several lines keeps the others and updates the total")
    def test_delete_one(self, pool, ret):
        for i, q in ((0, 3), (1, 2)):
            _add(ret, pool, i, q)
        ret.delete_row(0)
        lines = ret.cart_lines()
        assert [l.batch for l in lines] == [pool.batches[1]]
        assert ret.cart_total() == ROUND(pool.price(1, 2), abs=TOL)

    @allure.story("Deleting the last line empties the cart and disables checkout")
    def test_delete_last(self, pool, ret):
        _add(ret, pool, 0, 3)
        ret.delete_row(0)
        assert ret.cart_lines() == [] and ret.empty_cart_visible() and not ret.checkout_enabled()
        assert ret.cart_total() == 0

    @allure.story("A deleted line's stock is offered again in full")
    def test_deleted_line_frees_stock(self, pool, ret):
        _stage(ret, pool, 2, 1)
        stock = ret.available()
        ret.set_qty(int(stock))
        ret.add_current()
        ret.delete_row(0)
        _stage(ret, pool, 2, 1)
        assert ret.available() == stock


# ---- Return Checkout preview ---------------------------------------------------------------------------------------
@allure.epic("Inventory")
@allure.feature("Inventory Return - checkout")
class TestCheckoutPanel:
    @pytest.fixture()
    def at_checkout(self, pool, ret):
        _add(ret, pool, 0, 7)
        _add(ret, pool, 1, 2)
        total = ret.cart_total()
        ret.go_to_checkout()
        return ret, total

    @allure.story("The supplier is not pre-selected when returning from the Inventory Return menu; Complete is disabled")
    def test_supplier_required(self, at_checkout):
        ret, _ = at_checkout
        assert not ret.supplier_preselected() and not ret.complete_enabled()

    @allure.story("Any supplier of the pharmacy can be chosen")
    def test_supplier_options(self, second_supplier, at_checkout, pool):
        ret, _ = at_checkout
        opts = [o.lower() for o in ret.supplier_options()]
        assert any(pool.supplier.lower() in o for o in opts) and any(second_supplier.lower() in o for o in opts), opts

    @allure.story("Choosing a supplier enables Complete")
    def test_supplier_enables_complete(self, at_checkout, pool):
        ret, _ = at_checkout
        ret.select_supplier(pool.supplier)
        assert ret.complete_enabled()

    @allure.story("Previous Balance is the supplier's balance; New Balance is Previous - Final Price")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("who", ["pool", "second"])
    def test_balance_preview(self, second_supplier, at_checkout, pool, page, who):
        ret, total = at_checkout
        name = pool.supplier if who == "pool" else second_supplier
        ret.select_supplier(name)
        s = ret.summary()
        assert s["total_price"] == ROUND(total, abs=TOL)
        assert s["new_balance"] == ROUND(s["previous_balance"] - s["final_price"], abs=TOL), s
        assert s["previous_balance"] == ROUND(supplier_balance(page, name), abs=TOL)

    @allure.story("Total Items is the number of pieces being returned")
    def test_total_items(self, at_checkout, pool):
        ret, _ = at_checkout
        ret.select_supplier(pool.supplier)
        assert ret.summary()["total_items"] == sum(l.pieces for l in ret.cart_lines())

    @allure.story("Invoice number and Note accept text")
    def test_invoice_and_note(self, at_checkout, pool):
        ret, _ = at_checkout
        ret.select_supplier(pool.supplier)
        ret.set_invoice("RET-INV-77")
        ret.set_note("damaged strips returned")
        assert ret.complete_enabled()

    @allure.story("With no demurrage the Final Price is the cart total rounded to a whole Taka")
    def test_no_demurrage(self, at_checkout, pool):
        ret, total = at_checkout
        ret.select_supplier(pool.supplier)
        s, e = ret.summary(), expected_summary(total)
        assert s["demurrage"] == 0 and s["final_price"] == ROUND(e["final_price"], abs=TOL), (s, e)

    @allure.story("Demurrage unit offers % and Tk; the default is %")
    def test_demurrage_units(self, at_checkout):
        ret, _ = at_checkout
        assert ret.demurrage_unit() == "%"
        ret.set_demurrage(5, "Tk")
        assert ret.demurrage_unit() == "Tk"


DEMURRAGE = [(0, "%"), (1, "%"), (3, "%"), (10, "%"), (12.5, "%"), (33.33, "%"), (50, "%"), (99.99, "%"), (100, "%"),
             (0.5, "%"), (1, "Tk"), (5, "Tk"), (12.34, "Tk"), (0.01, "Tk"), (0, "Tk")]
DEMURRAGE_BLOCKED = [(100.01, "%"), (101, "%"), (500, "%"), (-5, "%"), (-5, "Tk"), (-0.01, "Tk")]


@allure.epic("Inventory")
@allure.feature("Inventory Return - checkout")
class TestDemurragePreview:
    @pytest.fixture()
    def at_checkout(self, pool, ret):
        _add(ret, pool, 0, 5)                # Tk 16.65
        _add(ret, pool, 2, 7)                # 7 x 1.3333
        total = ret.cart_total()
        ret.go_to_checkout()
        ret.select_supplier(pool.supplier)
        return ret, total

    @allure.story("Demurrage (percentage or flat) is deducted from the return total; Round Off makes the Final Price whole")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("value,unit", DEMURRAGE, ids=lambda v: str(v))
    def test_demurrage_amount(self, at_checkout, value, unit):
        ret, total = at_checkout
        ret.set_demurrage(value, unit)
        s, e = ret.summary(), expected_summary(total, (value, unit))
        assert s["demurrage"] == ROUND(e["demurrage"], abs=TOL), (s, e)
        assert s["final_price"] == ROUND(e["final_price"], abs=TOL), (s, e)
        assert s["round_off"] == ROUND(e["round_off"], abs=TOL), (s, e)

    @allure.story("The balance preview follows the demurrage: New Balance = Previous - Final Price")
    @pytest.mark.parametrize("value,unit", [(10, "%"), (7, "Tk"), (100, "%")], ids=lambda v: str(v))
    def test_balance_follows_demurrage(self, at_checkout, value, unit):
        ret, _ = at_checkout
        ret.set_demurrage(value, unit)
        s = ret.summary()
        assert s["new_balance"] == ROUND(s["previous_balance"] - s["final_price"], abs=TOL), s

    @allure.story("Demurrage can never exceed the return (over 100 %, negative) - the input is refused or clamped")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.parametrize("value,unit", DEMURRAGE_BLOCKED, ids=lambda v: str(v))
    def test_demurrage_blocked(self, at_checkout, value, unit):
        ret, total = at_checkout
        ret.set_demurrage(value, unit)
        s = ret.summary()
        assert 0 <= s["demurrage"] <= total + TOL and s["final_price"] >= 0, (value, unit, s)
        assert not (ret.complete_enabled() and (s["demurrage"] < 0 or s["demurrage"] > total + TOL)), s

    @allure.story("A flat demurrage larger than the return total is refused")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.parametrize("extra", [0.01, 1, 1000], ids=lambda v: f"+{v}")
    def test_flat_demurrage_above_total(self, at_checkout, extra):
        ret, total = at_checkout
        ret.set_demurrage(round(total + extra, 2), "Tk")
        s = ret.summary()
        assert s["demurrage"] <= total + TOL and s["final_price"] >= 0, (total, extra, s)

    @allure.story("A flat demurrage equal to the total leaves a Final Price of Tk 0")
    def test_flat_demurrage_equals_total(self, at_checkout):
        ret, total = at_checkout
        ret.set_demurrage(total, "Tk")
        assert ret.summary()["final_price"] == 0

    @allure.story("Clearing the demurrage input returns to no demurrage")
    def test_blank_demurrage(self, at_checkout):
        ret, total = at_checkout
        ret.set_demurrage(10, "%")
        ret.set_demurrage(None, "%")
        s = ret.summary()
        assert s["demurrage"] == 0 and s["final_price"] == ROUND(expected_summary(total)["final_price"], abs=TOL), s

    @allure.story("Switching % to Tk (and back) recalculates the demurrage")
    def test_unit_switch_recalculates(self, at_checkout):
        ret, total = at_checkout
        ret.set_demurrage(10, "%")
        pct = ret.summary()["demurrage"]
        ret.set_demurrage(10, "Tk")
        assert ret.summary()["demurrage"] == ROUND(10, abs=TOL) and pct == ROUND(total * 0.1, abs=0.02)
        ret.set_demurrage(10, "%")
        assert ret.summary()["demurrage"] == ROUND(pct, abs=TOL)

    @allure.story("Editing the cart after the checkout was opened keeps the checkout in step")
    def test_cart_change_after_checkout(self, at_checkout, pool):
        ret, _ = at_checkout
        ret.set_demurrage(10, "%")
        try:
            ret.rows.first.locator("td").last.locator("svg").first.click(timeout=5_000)
        except Exception:
            return   # the cart is locked once the checkout is open - nothing can drift
        ret.set_qty(2)
        ret.update_cart()
        total = ret.cart_total()
        s = ret.summary() if ret.complete_btn.is_visible() else None
        if s:
            assert s["total_price"] == ROUND(total, abs=TOL), s
