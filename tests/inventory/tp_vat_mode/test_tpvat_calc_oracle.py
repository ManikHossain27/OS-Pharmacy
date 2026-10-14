"""TP/VAT inventory mode - calculation model (no browser).

Verifies ``utils/tpvat_calc.py`` against
  * every worked example in Inventory Management.md (sections 10-13, 38-41),
  * the real numbers in the user's workbook sheet 'TP per vat mode (2)',
  * invariants over the full combination matrix and over random 200-500 product inventories.
``tools/validate_tpvat_oracle.py`` additionally proves the oracle against the recalculated workbook
(cell by cell), so a green run here means the UI tests compare against the workbook's own mathematics.
"""
from __future__ import annotations

import random

import allure
import pytest

from utils.tpvat_calc import SYSTEM_VAT_RATE, TpVatLine, build, vat_for
from utils.tpvat_scenarios import calc_matrix

pytestmark = [pytest.mark.inventory, pytest.mark.calc]

TOL = 1e-6


def _random_inventory(rng: random.Random, n: int, free_ratio: float = 0.2, special_ratio: float = 0.0):
    out = []
    for _ in range(n):
        tp = round(rng.uniform(1, 800), 2)
        out.append(TpVatLine(
            box_qty=rng.choice([0.5, 1, 2, 3, 5, 10, 25]), qty_per_box=rng.choice([1, 2, 6, 10, 12, 20, 60]),
            tp_per_box=tp, vat_per_box=vat_for(tp) if rng.random() < 0.7 else round(rng.uniform(0, 100), 2),
            free_qty=rng.choice([1, 5, 10]) if rng.random() < free_ratio else 0,
            retail_per_box=round(rng.uniform(900, 1200), 2), wholesale_per_box=round(rng.uniform(850, 1100), 2),
            special_discount=round(rng.uniform(1, 30), 2) if rng.random() < special_ratio else 0))
    return out


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - calculation model")
class TestSpecWorkedExamples:

    @allure.story("Spec 11: system VAT is 17.4 % - TP/Box 100 pre-fills VAT/Box 17.40")
    def test_system_vat_rate(self):
        assert SYSTEM_VAT_RATE == 0.174 and vat_for(100) == 17.4

    @pytest.mark.parametrize("tp,vat", [(89.44, 15.56), (28.36, 4.93), (0.01, 0.0), (12345.67, 2148.15)])
    @allure.story("Sheet H: VAT/Box = ROUND(TP/Box x 17.4 %, 2)  (verified live: 89.44 -> 15.56, 28.36 -> 4.93)")
    def test_vat_for(self, tp, vat):
        assert vat_for(tp) == pytest.approx(vat, abs=0.0051)

    @allure.story("Spec 13: Total Purchase Amount = (TP/Box + VAT/Box) x Box Qty")
    def test_total_price(self):
        l = build([TpVatLine(3, 10, 100, 17.4)]).lines[0]
        assert l.total_price == pytest.approx((100 + 17.4) * 3)

    @allure.story("Spec 5.3 / sheet D: Total Qty = Box Qty x Qty/Box")
    def test_total_qty(self):
        assert build([TpVatLine(3, 10, 50, 5)]).lines[0].total_qty == 30

    @allure.story("Spec 12 / 41: TP/Box = 0 with VAT/Box = 5 is a valid line; Total Price = VAT x boxes")
    def test_tp_zero_vat_only_total(self):
        inv = build([TpVatLine(2, 10, 0, 5)])
        assert inv.total_price == 10 and inv.total_tp == 0 and inv.total_vat == 10

    @allure.story("Spec 41: a zero-TP line must get a purchase price from the available values (VAT only: 10 / 20 = 0.50)")
    def test_tp_zero_purchase_price_spec_rule(self):
        l = build([TpVatLine(2, 10, 0, 5)], less_rule="total").lines[0]       # rule that avoids the sheet's blank Z
        assert l.purchase_price_pc == pytest.approx(0.5)

    @allure.story("WORKBOOK GAP TPVAT-2: the sheet's col T is #VALUE! for a TP/Box = 0 line (Less/product Z is blank when J = 0)")
    def test_tp_zero_sheet_error(self):
        l = build([TpVatLine(2, 10, 0, 5), TpVatLine(1, 10, 50, 8.7)]).lines[0]
        assert l.sheet_error == "#VALUE!" and l.purchase_price_pc is None

    @allure.story("Sheet AC/T and the application: VAT is charged on free pieces too (15+10)x2 + 1.00x10 = 60; 60/30 = 2.00")
    def test_free_qty_vat_is_charged_on_free_pieces(self):
        l = build([TpVatLine(2, 10, 15, 10, free_qty=10)]).lines[0]
        assert l.total_price == 60 and l.purchase_price_pc == pytest.approx(2.0) and l.purchase_price_box == pytest.approx(20.0)

    @allure.story("Knowledge-file example 38/40 ((15+10) x 2 / 30 = 1.66) holds only when VAT on free pieces is ignored")
    def test_knowledge_file_example_needs_free_vat_off(self):
        l = build([TpVatLine(2, 10, 15, 10, free_qty=10)], free_vat=False).lines[0]
        assert l.purchase_price_pc == pytest.approx(50 / 30)
        assert build([TpVatLine(2, 10, 15, 10)]).lines[0].purchase_price_pc == pytest.approx(2.5)   # without free: Tk 2.50

    @allure.story("Spec 38: the discount applies on TP only - VAT is never discounted (10 % of TP 200 = 20, VAT 34.8 untouched)")
    def test_discount_on_tp_only(self):
        inv = build([TpVatLine(2, 10, 100, 17.4)], pct=10)
        assert inv.total_discount == pytest.approx(20) and inv.total_vat == pytest.approx(34.8)
        assert inv.final_price == 215          # ROUND(234.80 - 20) - verified live (Round Off 0.20)
        assert inv.round_adjustment == pytest.approx(0.2)

    @allure.story("Spec 38/39: lines with Free Qty are excluded from the discount base")
    def test_free_line_excluded(self):
        inv = build([TpVatLine(2, 10, 100, 17.4), TpVatLine(3, 10, 21.6, 3.76, free_qty=5)], pct=10)
        assert inv.lines[1].discount_value == 0 and inv.lines[0].discount_value == pytest.approx(20)

    @allure.story("Spec 39: a Flat discount is spread over eligible TP and sums exactly to the flat amount")
    def test_flat_spread(self):
        inv = build([TpVatLine(2, 10, 100, 17.4), TpVatLine(1, 10, 300, 52.2)], flat=50)
        assert inv.total_discount == pytest.approx(50)
        assert inv.lines[0].discount_value / inv.lines[1].discount_value == pytest.approx(200 / 300)

    @allure.story("Special (Tk) per-line discount overrides % and flat; the % / flat base excludes that line")
    def test_special_overrides(self):
        inv = build([TpVatLine(2, 10, 100, 17.4, special_discount=20), TpVatLine(3, 10, 125.75, 21.88)], pct=10)
        a, b = inv.lines
        assert a.discount_value == 20 and a.discount_pct == pytest.approx(0.1)
        assert b.discount_value == pytest.approx(37.725) and inv.general_discount == pytest.approx(37.725)
        assert inv.sum_special_applied == 20

    @allure.story("Flat discount is reduced by the specials first (sheet: MAX(flat - SUM(S), 0) / eligible TP)")
    def test_flat_minus_special(self):
        inv = build([TpVatLine(2, 10, 100, 17.4, special_discount=20), TpVatLine(3, 10, 125.75, 21.88)], flat=50)
        assert inv.lines[1].discount_value == pytest.approx(30) and inv.total_discount == pytest.approx(50)

    @allure.story("Sheet K2/K3: Final Price = ROUND(Total - Discount, 0); Round Off = Final - (Total - Discount)")
    def test_final_price_rounded(self):
        inv = build([TpVatLine(2, 10, 89.44, 15.56), TpVatLine(1, 5, 33.33, 5.80)], pct=7.5)
        assert float(inv.final_price).is_integer()
        assert inv.round_adjustment == pytest.approx(inv.final_price - (inv.total_price - inv.total_discount))

    @allure.story("Sheet AA: the Round Off is shared over TP AFTER discount, so line costs add up to the Final Price")
    def test_round_off_share_reconciles(self):
        inv = build([TpVatLine(2, 10, 89.44, 15.56), TpVatLine(3, 12, 125.75, 21.88, free_qty=5),
                     TpVatLine(1, 1, 80, 13.92)], pct=7.5)
        assert sum(l.final_line_cost for l in inv.lines) == pytest.approx(inv.final_price, abs=1e-6)

    @allure.story("Workbook sample rows (TP per vat mode (2) rows 8-10, 12 % discount): oracle == recalculated sheet")
    def test_workbook_sample(self):
        lines = [TpVatLine(2, 1, 89.44, 45, retail_per_box=150, wholesale_per_box=150),
                 TpVatLine(5, 10, 68.14, 20, free_qty=2, retail_per_box=100, wholesale_per_box=90),
                 TpVatLine(10, 4, 143.92, 25.04, special_discount=65, retail_per_box=192, wholesale_per_box=190)]
        inv = build(lines, pct=12, paid=4563)
        assert inv.total_tp == pytest.approx(2 * 89.44 + 5 * 68.14 + 10 * 143.92)
        assert inv.final_price == pytest.approx(round(inv.total_price - inv.total_discount))
        assert sum(l.final_line_cost for l in inv.lines) == pytest.approx(inv.final_price, abs=1e-6)

    @allure.story("Supplier balance (sheet M3/M4): Due = MAX(balance + Final - Paid, 0), Advance = MAX(-(...), 0)")
    @pytest.mark.parametrize("bal,paid,due,adv", [(0, 0, 215, 0), (0, 215, 0, 0), (0, 300, 0, 85), (-100, 0, 115, 0),
                                                  (-300, 0, 0, 85), (50, 100, 165, 0)])
    def test_due_advance(self, bal, paid, due, adv):
        inv = build([TpVatLine(2, 10, 100, 17.4)], pct=10, paid=paid, supplier_balance=bal)
        assert (inv.due, inv.advance) == (pytest.approx(due), pytest.approx(adv))

    @allure.story("TP/VAT sheet gap TPVAT-1: M3/M4 do NOT deduct 'Less' (the Default sheet was updated to do so)")
    def test_sheet_ignores_less_in_due(self):
        inv = build([TpVatLine(2, 10, 100, 17.4)], paid=100, less=50)
        assert inv.due == pytest.approx(inv.final_price - 100)        # Default mode would give final - 100 - 50


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - calculation model")
class TestCombinationMatrix:
    """Every combination of qty/box x box qty x TP x VAT mode x free qty x discount (~3,500 inventories)."""

    @staticmethod
    def _check(inv, lines):
        errs = []
        if abs(sum(l.discount_value for l in inv.lines) - inv.total_discount) > TOL:
            errs.append("line discounts do not sum to the total discount")
        if any(l.free_qty > 0 and l.special_discount <= 0 and l.discount_value != 0 for l in inv.lines):
            errs.append("a free-qty line received a discount")
        if abs((inv.total_vat) - sum(l.total_vat for l in inv.lines)) > TOL:
            errs.append("VAT was altered by the discount")
        if abs(inv.final_price - round(inv.final_price)) > TOL:
            errs.append("final price is not whole")
        if abs((inv.total_price - inv.total_discount + inv.round_adjustment) - inv.final_price) > TOL:
            errs.append("Total - Discount + Round Off != Final")
        ok = [l for l in inv.lines if l.purchase_price_pc is not None and l.total_qty > 0]
        if len(ok) == len(inv.lines) and inv.total_tp - inv.total_discount != 0:
            if abs(sum(l.final_line_cost or 0 for l in inv.lines) - inv.final_price) > 1e-4:
                if all(l.final_line_cost is not None for l in inv.lines):
                    errs.append("line costs do not add up to the Final Price")
        return errs

    @allure.story("Totals, discount, VAT and round-off invariants hold for every combination")
    def test_matrix_invariants(self):
        bad, n = [], 0
        for cid, lines, pct, flat in calc_matrix():
            n += 1
            inv = build(lines, pct=pct, flat=flat)
            for e in self._check(inv, lines):
                bad.append(f"{cid}: {e}")
        assert n > 3000, f"matrix unexpectedly small: {n}"
        assert not bad, f"{len(bad)} violations, first: {bad[:5]}"

    @allure.story("Flat discount equals the flat amount whenever an eligible line exists and the flat does not exceed its TP")
    def test_flat_exact(self):
        bad = []
        for cid, lines, pct, flat in calc_matrix():
            if not flat:
                continue
            inv = build(lines, flat=flat)
            elig_tp = sum(l.total_tp for l in lines if l.free_qty <= 0 and l.special_discount <= 0)
            specials = sum(l.special_discount for l in lines if l.special_discount > 0)
            if elig_tp > 0:
                want = specials + max(flat - specials, 0)
                if abs(inv.total_discount - want) > 1e-6:
                    bad.append((cid, inv.total_discount, want))
        assert not bad, bad[:5]


@allure.epic("Inventory")
@allure.feature("TP/VAT mode - calculation model")
class TestLargeInventories:

    @pytest.mark.parametrize("n,seed", [(200, 1), (300, 2), (500, 3)])
    @pytest.mark.parametrize("pct,flat", [(0, 0), (10, 0), (7.5, 0), (0, 500), (0, 12345.67)])
    @allure.story("200 / 300 / 500-product inventories reconcile under every discount type (with specials and free qty)")
    def test_large_inventory(self, n, seed, pct, flat):
        inv = build(_random_inventory(random.Random(seed), n, free_ratio=0.2, special_ratio=0.1), pct=pct, flat=flat)
        assert len(inv.lines) == n
        assert abs(inv.total_price - sum(l.total_price or 0 for l in inv.lines)) < 1e-6
        assert abs(inv.total_vat - (inv.total_price - inv.total_tp)) < 1e-6
        assert float(inv.final_price).is_integer()
        sums = sum(l.discount_value for l in inv.lines)
        assert abs(sums - inv.total_discount) < 1e-6
        assert all(l.discount_value == 0 for l in inv.lines if l.free_qty > 0 and l.special_discount <= 0)
        if flat and inv.eligible_tp > 0:
            assert abs(inv.total_discount - (inv.sum_special + max(flat - inv.sum_special, 0))) < 1e-6
        costs = [l.final_line_cost for l in inv.lines]
        assert all(c is not None for c in costs)
        assert abs(sum(costs) - inv.final_price) < 1e-4, f"line costs {sum(costs)} != Final Price {inv.final_price}"
