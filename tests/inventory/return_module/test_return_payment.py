"""Inventory Return from a record whose inventory was bought on different terms: partly paid, unpaid, with an inventory
discount, with Free Qty, and with an expiry date. The return is priced at each line's purchase price (final cost after
discount), and the supplier balance moves by the Final Price whatever was paid."""
from __future__ import annotations

import os

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage
from pages.inventory_return_page import InventoryReturnPage
from tests.inventory.return_module.helpers import TOL, batch_stock, checkout_and_complete, expected_summary, supplier_balance

ROUND = pytest.approx

TERMS = {
    "half-paid": ("two_plain", dict(paid_ratio=0.5, choice="Due & Buy")),
    "unpaid": ("two_plain", dict(paid_ratio=0.0, choice="Due & Buy")),
    "discount-10pct": ("two_plain", dict(discount=(10, "%"))),
    "discount-7.5pct-half-paid": ("two_plain", dict(discount=(7.5, "%"), paid_ratio=0.5, choice="Due & Buy")),
    "free-qty": ("two_one_free", dict()),
    "all-free-lines": ("all_free", dict()),
    "expiry": ("large_qty_with_expiry", dict()),
}


@pytest.fixture(params=list(TERMS), ids=list(TERMS))
def bought(request, create):
    shape, kw = TERMS[request.param]
    if os.getenv("QA_NO_CASH"):       # a new pharmacy has no Cash balance: every purchase is bought on credit
        kw = {**kw, "paid_ratio": 0.0, "choice": "Due & Buy"}
    return request.param, create(shape, **kw)


def _status(page, saved) -> str:
    rec = InventoryRecordPage(page).open()
    row = rec.row_by_inventory_id(saved.inventory_id)
    row.wait_for(state="visible", timeout=30_000)
    return rec.status_cell_text(row)


@allure.epic("Inventory")
@allure.feature("Inventory Return - purchase terms")
class TestReturnByPurchaseTerms:
    @allure.story("The pre-loaded cart is priced at the inventory's final cost (after discount), whatever was paid")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cart_priced_at_final_cost(self, page, bought):
        name, saved = bought
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        lines = saved.journey.inventory.lines
        cart = ret.cart_lines()
        assert len(cart) == len(lines), cart
        for c, o in zip(cart, lines):
            if o.free_qty:       # free pieces are priced at the batch's regular per-piece price (owner); the pieces offered are BUG-INV-050
                assert c.price / c.pieces == ROUND(o.final_line_cost / o.total_qty, abs=0.01), (name, c.price, c.pieces, o.final_line_cost)
            else:
                assert c.price == ROUND(o.final_line_cost, abs=0.03), (name, c.price, o.final_line_cost)

    @allure.story("A full return moves the supplier balance by the Final Price, empties the batches and marks the record Returned")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("demurrage", [None, (10, "%")], ids=["nodem", "dem10pct"])
    def test_full_return(self, page, bought, catalogue, demurrage):
        name, saved = bought
        bal = supplier_balance(page, saved.supplier)
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        done = checkout_and_complete(ret, saved.supplier, demurrage)
        assert done.status in (200, 201), (name, done.status, done.body[:200])
        assert done.summary["final_price"] == ROUND(expected_summary(done.cart_total, demurrage)["final_price"], abs=TOL), done.summary
        assert supplier_balance(page, saved.supplier) == ROUND(bal - done.summary["final_price"], abs=TOL), (name, bal)
        check = InventoryReturnPage(page).open()
        for spec, batch in zip(saved.journey.specs, saved.journey.batches):
            assert not batch_stock(check.open(), catalogue[int(spec.product[1:])], batch), (name, batch)
        assert "return" in _status(page, saved).lower(), name

    @allure.story("Free pieces are returned at the batch's regular per-piece purchase price (product owner)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("terms", ["free-qty", "all-free-lines"])
    def test_free_pieces_offered(self, page, create, terms):
        shape, kw = TERMS[terms]
        if os.getenv("QA_NO_CASH"):
            kw = {**kw, "paid_ratio": 0.0, "choice": "Due & Buy"}
        saved = create(shape, **kw)
        ret = InventoryReturnPage(page).open_for(InventoryRecordPage(page).open(), saved.inventory_id)
        for c, o in zip(ret.cart_lines(), saved.journey.inventory.lines):
            assert c.pieces == o.total_qty + o.free_qty, (terms, c.pieces, o.total_qty, o.free_qty)
            per_piece = o.final_line_cost / o.total_qty
            assert c.price == ROUND(per_piece * c.pieces, abs=0.05), (terms, c.price, per_piece, c.pieces)
