"""Completing and cancelling an Inventory Return from the Inventory Return menu.

Every case reads the batch stock, the supplier balances and the Return Record tiles BEFORE and AFTER, so the pool's size
and earlier returns do not matter. Spec ('Return Checkout' / 'Return Details and Return Cancellation'): the final return
amount (total - demurrage) is added to the Pharmacy Wallet and reduces the Supplier Balance; the returned quantity is
deducted from the batch; cancelling a return reverses all of it. Demurrage is the pharmacy's business loss: the supplier
credits only the final amount.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import allure
import pytest

from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from tests.inventory.return_module.helpers import (
    TOL, batch_stock, checkout_and_complete, detail, expected_summary, supplier_balance)

ROUND = pytest.approx


@dataclass
class Snapshot:
    stock: list[float | None]
    balances: dict[str, float]
    tiles: dict
    treasury: float | None = None


def _num(text: str) -> float:
    import re
    m = re.search(r"-?[\d,]+(?:\.\d+)?", text or "")
    return float(m.group().replace(",", "")) if m else float("nan")


def snapshot(page, pool, lines: list[int], suppliers: list[str]) -> Snapshot:
    """Stock of the batches in ``lines`` (indexes into the pool), the suppliers' balances and the Return Record tiles."""
    ret = InventoryReturnPage(page).open()
    stock = [batch_stock(ret, pool.products[i], pool.batches[i]) for i in lines]
    balances = {s: supplier_balance(page, s) for s in suppliers}
    tiles = InventoryReturnRecordPage(page).open().summary()
    return Snapshot(stock, balances, tiles)


def treasury(page) -> float:
    """Dashboard 'Total Treasury'."""
    page.goto("/dashboard")
    page.get_by_text("Total Treasury").first.wait_for(state="visible", timeout=90_000)
    page.wait_for_timeout(3000)
    text = page.locator("body").inner_text()
    return _num(text[text.index("Total Treasury"):].split("Total Treasury", 1)[1])


@dataclass
class Case:
    id: str
    items: list[tuple[int, float, str]]      # (pool line, qty, 'pc'|'box')
    demurrage: tuple | None = None
    to_second: bool = False
    invoice: str = ""
    note: str = ""


CASES = [
    Case("1pc", [(0, 1, "pc")]),
    Case("7pc-p1", [(1, 7, "pc")]),
    Case("1box", [(0, 1, "box")]),
    Case("3box-p2", [(2, 3, "box")]),
    Case("pc-10pct", [(0, 5, "pc")], (10, "%")),
    Case("pc-tk5", [(0, 5, "pc")], (5, "Tk")),
    Case("box-12.5pct", [(0, 2, "box")], (12.5, "%")),
    Case("three-products", [(0, 4, "pc"), (1, 2, "pc"), (2, 1, "box")], (3, "%")),
    Case("three-products-boxes", [(0, 1, "box"), (2, 2, "box")], (20, "Tk")),
    Case("second-supplier", [(0, 5, "pc")], (10, "%"), to_second=True),
    Case("second-supplier-multi", [(0, 3, "pc"), (1, 4, "pc")], None, to_second=True),
    Case("small-33pct", [(1, 1, "pc")], (33.33, "%")),
    Case("invoice-note", [(0, 2, "pc")], (2, "Tk"), invoice="RET-INV-901", note="expired strips"),
    Case("large-1000pc", [(0, 1000, "pc")], (1, "%")),
    Case("half-penny-rounding", [(0, 3, "pc")], (3, "%")),
]


def _price(pool, items) -> float:
    return round(sum(pool.price(i, q * (pool.qty_per_box[i] if u == "box" else 1)) for i, q, u in items), 2)


@allure.epic("Inventory")
@allure.feature("Inventory Return - complete")
class TestCompleteReturn:
    @allure.story("A completed return deducts the batch stock, credits the supplier the FINAL amount, and is recorded")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    def test_return(self, page, pool, second_supplier, case: Case):
        supplier = second_supplier if case.to_second else pool.supplier
        other = pool.supplier if case.to_second else second_supplier
        lines = sorted({i for i, _, _ in case.items})
        total = _price(pool, case.items)
        demurrage = (total, "Tk") if case.demurrage and case.demurrage[0] == "TOTAL" else case.demurrage
        before = snapshot(page, pool, lines, [supplier, other])
        ret = InventoryReturnPage(page).open()
        for i, q, u in case.items:
            ret.add_line(pool.products[i], pool.batches[i], q, u)
        done = checkout_and_complete(ret, supplier, demurrage, invoice=case.invoice, note=case.note)
        exp = expected_summary(done.cart_total, demurrage)

        with allure.step("The checkout figures and the server response"):
            assert done.cart_total == ROUND(total, abs=0.03), (done.cart_total, total)
            assert done.summary["final_price"] == ROUND(exp["final_price"], abs=TOL), (done.summary, exp)
            assert done.status in (200, 201), (done.status, done.body[:300])
            body = json.loads(done.body) if done.body.startswith("{") else {}
            assert "successfully" in done.toast.lower(), done.toast
            if body:
                assert body.get("finalPrice") == ROUND(exp["final_price"], abs=TOL), body
                assert body.get("demurrageAmount", 0) == ROUND(exp["demurrage"], abs=TOL), body
        after = snapshot(page, pool, lines, [supplier, other])

        with allure.step("Batch stock is deducted"):
            for idx, i in enumerate(lines):
                pieces = sum(q * (pool.qty_per_box[i] if u == "box" else 1) for j, q, u in case.items if j == i)
                assert after.stock[idx] == before.stock[idx] - pieces, (pool.batches[i], before.stock, after.stock)
        with allure.step("The supplier is credited the final amount; the other supplier is untouched"):
            assert after.balances[supplier] == ROUND(before.balances[supplier] - exp["final_price"], abs=TOL), \
                (before.balances, after.balances, exp)
            assert after.balances[other] == ROUND(before.balances[other], abs=TOL)
        with allure.step("The Return Record shows the return and its tiles move"):
            row = InventoryReturnRecordPage(page).open().first_row()
            assert row["supplier"].lower().startswith(supplier.lower()[:8]) and row["status"] == "Returned", row
            assert row["price"] == ROUND(exp["final_price"], abs=TOL), row
            assert row["items"].startswith(str(len(case.items))), row
            assert after.tiles["returns_count"] == before.tiles["returns_count"] + 1, (before.tiles, after.tiles)
            assert after.tiles["returns_total"] == ROUND(before.tiles["returns_total"] + exp["final_price"], abs=1.01)
            assert after.tiles["demurrage_total"] == ROUND(before.tiles["demurrage_total"] + exp["demurrage"], abs=1.01)

    @allure.story("A return with Final Price 0 (100 % or flat demurrage = total) is refused cleanly - never a server error, never saved")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.parametrize("mode", ["100pct", "tk-equals-total"])
    def test_zero_final_refused(self, page, pool, mode):
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 3, "pc")
        total = ret.cart_total()
        ret.go_to_checkout()
        ret.select_supplier(pool.supplier)
        ret.set_demurrage(*((100, "%") if mode == "100pct" else (total, "Tk")))
        if not ret.complete_enabled():
            return
        status, body = ret.complete()
        assert status is not None and 400 <= status < 500, (status, body[:200])
        assert "successfully" not in ret.toast_text().lower()

    @allure.story("Return Details show the supplier, quantities, prices, demurrage and the final amount (spec)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_details(self, page, pool):
        items = [(0, 4, "pc"), (1, 2, "pc")]
        ret = InventoryReturnPage(page).open()
        for i, q, u in items:
            ret.add_line(pool.products[i], pool.batches[i], q, u)
        done = checkout_and_complete(ret, pool.supplier, (10, "%"), invoice="RET-DET-1")
        exp = expected_summary(done.cart_total, (10, "%"))
        rec = InventoryReturnRecordPage(page).open()
        text = rec.open_details(rec.rows.first)
        assert pool.supplier in text and "Returned" in detail(text, "Status")
        assert _num(detail(text, "Total Return Value")) == ROUND(done.cart_total, abs=TOL), text[:800]
        assert _num(detail(text, "Demurrage (")) == ROUND(exp["demurrage"], abs=TOL), text[:800]
        assert _num(detail(text, "Final Price")) == ROUND(exp["final_price"], abs=TOL), text[:800]
        assert pool.batches[0] in text and pool.batches[1] in text

    @allure.story("Completing a return credits the Pharmacy Wallet (Dashboard Total Treasury) with the final amount (spec)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_wallet_credited(self, page, pool):
        before = treasury(page)
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 20, "pc")
        done = checkout_and_complete(ret, pool.supplier, (5, "%"))
        after = treasury(page)
        assert after == ROUND(before + done.summary["final_price"], abs=TOL), \
            f"BUG-INV-028: Total Treasury {before} -> {after}, expected +{done.summary['final_price']}"

    @allure.story("The checkout's balance preview equals the balance the Supplier List shows after completing")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("to_second", [False, True], ids=["pool-supplier", "second-supplier"])
    def test_preview_matches_result(self, page, pool, second_supplier, to_second):
        supplier = second_supplier if to_second else pool.supplier
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[1], pool.batches[1], 6, "pc")
        done = checkout_and_complete(ret, supplier, (15, "%"))
        assert supplier_balance(page, supplier) == ROUND(done.summary["new_balance"], abs=TOL), done.summary

    @allure.story("A supplier with an Advance balance gets a bigger Advance; one with Due gets a smaller Due (signed balance)")
    def test_balance_signs(self, page, pool, second_supplier):
        for supplier in (pool.supplier, second_supplier):
            before = supplier_balance(page, supplier)
            ret = InventoryReturnPage(page).open()
            ret.add_line(pool.products[0], pool.batches[0], 10, "pc")
            done = checkout_and_complete(ret, supplier)
            assert supplier_balance(page, supplier) == ROUND(before - done.summary["final_price"], abs=TOL), (supplier, before)

    @allure.story("Two returns in a row each deduct their own quantity and credit their own amount")
    def test_two_returns_in_a_row(self, page, pool):
        before = snapshot(page, pool, [0], [pool.supplier])
        paid = 0.0
        for qty in (4, 9):
            ret = InventoryReturnPage(page).open()
            ret.add_line(pool.products[0], pool.batches[0], qty, "pc")
            paid += checkout_and_complete(ret, pool.supplier).summary["final_price"]
        after = snapshot(page, pool, [0], [pool.supplier])
        assert after.stock[0] == before.stock[0] - 13
        assert after.balances[pool.supplier] == ROUND(before.balances[pool.supplier] - paid, abs=TOL)
        assert after.tiles["returns_count"] == before.tiles["returns_count"] + 2

    @allure.story("After a return the form is reset: empty cart and no supplier carried over")
    def test_form_reset_after_return(self, page, pool):
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[2], pool.batches[2], 3, "pc")
        checkout_and_complete(ret, pool.supplier, (5, "%"))
        assert ret.empty_cart_visible() and ret.cart_lines() == [] and not ret.checkout_enabled()

    @allure.story("Completing twice quickly does not create two returns")
    @pytest.mark.negative
    def test_double_click_complete(self, page, pool):
        before = InventoryReturnRecordPage(page).open().summary()
        ret = InventoryReturnPage(page).open()
        ret.add_line(pool.products[0], pool.batches[0], 2, "pc")
        ret.go_to_checkout()
        ret.select_supplier(pool.supplier)
        ret.complete_btn.dblclick()
        page.wait_for_timeout(8000)
        after = InventoryReturnRecordPage(page).open().summary()
        assert after["returns_count"] == before["returns_count"] + 1, (before, after)


@allure.epic("Inventory")
@allure.feature("Inventory Return - cancel")
class TestCancelReturn:
    def _make(self, page, pool, items, supplier, demurrage=None):
        ret = InventoryReturnPage(page).open()
        for i, q, u in items:
            ret.add_line(pool.products[i], pool.batches[i], q, u)
        done = checkout_and_complete(ret, supplier, demurrage)
        rec = InventoryReturnRecordPage(page).open()
        return done, rec.first_row()

    @allure.story("Cancelling a return restores the batch stock and the supplier balance (spec)")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("items,demurrage", [([(0, 5, "pc")], None), ([(0, 2, "box"), (1, 3, "pc")], (10, "%")),
                                                 ([(2, 6, "pc")], (4, "Tk"))], ids=["plain", "two-lines-10pct", "tk4"])
    def test_cancel_restores(self, page, pool, items, demurrage):
        lines = sorted({i for i, _, _ in items})
        before = snapshot(page, pool, lines, [pool.supplier])
        done, row = self._make(page, pool, items, pool.supplier, demurrage)
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(row["id"])
        after = snapshot(page, pool, lines, [pool.supplier])
        assert after.stock == before.stock, (before.stock, after.stock)
        assert after.balances[pool.supplier] == ROUND(before.balances[pool.supplier], abs=TOL), (before.balances, after.balances)
        cancelled = InventoryReturnRecordPage(page).open().row_values(InventoryReturnRecordPage(page).row_by_id(row["id"]))
        assert cancelled["status"] == "Cancelled", cancelled

    @allure.story("A Cancelled return is left out of the Total Returns / Total Demurrage tiles (the app's own copy says so)")
    @pytest.mark.negative
    def test_tiles_exclude_cancelled(self, page, pool):
        done, row = self._make(page, pool, [(0, 5, "pc")], pool.supplier, (10, "%"))
        rec = InventoryReturnRecordPage(page).open()
        mid = rec.summary()
        rec.cancel_return(row["id"])
        rec.open()
        end = rec.summary()
        assert end["returns_count"] == mid["returns_count"] - 1, (mid, end)
        assert end["returns_total"] == ROUND(mid["returns_total"] - row["price"], abs=1.01), (mid, end)

    @allure.story("A Cancelled return offers View Details only and cannot be cancelled twice")
    @pytest.mark.negative
    def test_cancelled_row_menu(self, page, pool):
        done, row = self._make(page, pool, [(0, 2, "pc")], pool.supplier)
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(row["id"])
        rec.open()
        items = rec.menu_items(rec.row_by_id(row["id"]))
        assert "Cancel Return" not in items, items

    @allure.story("The Cancelled status filter lists the cancelled return")
    def test_status_filter_cancelled(self, page, pool):
        done, row = self._make(page, pool, [(0, 2, "pc")], pool.supplier)
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(row["id"])
        rec.open()
        rec.choose_status("Cancelled")
        ids = [r["id"] for r in rec.all_rows()]
        assert row["id"] in ids and all(r["status"] == "Cancelled" for r in rec.all_rows())

    @allure.story("Return Details of a cancelled return show the Cancelled status")
    def test_cancelled_details(self, page, pool):
        done, row = self._make(page, pool, [(0, 2, "pc")], pool.supplier, (5, "%"))
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(row["id"])
        rec.open()
        text = rec.open_details(rec.row_by_id(row["id"]))
        assert "Cancelled" in detail(text, "Status"), text[:600]

    @allure.story("Cancelling a return reverses the Pharmacy Wallet credit")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_cancel_reverses_wallet(self, page, pool):
        t0 = treasury(page)
        done, row = self._make(page, pool, [(0, 20, "pc")], pool.supplier)
        InventoryReturnRecordPage(page).open().cancel_return(row["id"])
        assert treasury(page) == ROUND(t0, abs=TOL), "Total Treasury did not return to its previous value"

    @allure.story("Cancelling one return leaves another return untouched")
    def test_cancel_one_of_two(self, page, pool):
        d1, r1 = self._make(page, pool, [(0, 3, "pc")], pool.supplier)
        d2, r2 = self._make(page, pool, [(0, 4, "pc")], pool.supplier)
        rec = InventoryReturnRecordPage(page).open()
        rec.cancel_return(r1["id"])
        rec.open()
        states = {r["id"]: r["status"] for r in rec.all_rows()}
        assert states[r1["id"]] == "Cancelled" and states[r2["id"]] == "Returned", states
