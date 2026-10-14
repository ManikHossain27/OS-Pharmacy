"""Default inventory mode - calculation model (no browser).

Verifies the oracle (utils/inventory_calc.py) against
  * every worked example in Inventory Management.md,
  * the real numbers in the user's workbook (both sheets),
  * invariants over the full combination matrix and over random 200-500
    product inventories.
tools/validate_inventory_oracle.py additionally proves the oracle against the
recalculated workbook itself (cell-by-cell), so a green run here means the UI
tests are comparing against the workbook's own mathematics.
"""
from __future__ import annotations

import random

import allure
import pytest

from utils.inventory_calc import Line, build
from utils.inventory_scenarios import calc_matrix

pytestmark = [pytest.mark.inventory, pytest.mark.calc]

TOL = 1e-6


def _fails(items, check):
    out = []
    for item in items:
        msg = check(item)
        if msg:
            out.append(f"{item[0]}: {msg}")
    return out


def _random_inventory(rng: random.Random, n: int, free_ratio: float = 0.2):
    return [Line(box_qty=rng.choice([0.5, 1, 2, 3, 5, 10, 25]), qty_per_box=rng.choice([1, 2, 6, 10, 12, 20, 60]),
                 btp_vat_per_box=round(rng.uniform(1, 900), 2),
                 free_qty=rng.choice([1, 5, 10]) if rng.random() < free_ratio else 0,
                 retail_per_box=round(rng.uniform(900, 1200), 2), wholesale_per_box=round(rng.uniform(850, 1100), 2))
            for _ in range(n)]


@allure.epic("Inventory")
@allure.feature("Default mode - calculation model")
class TestSpecWorkedExamples:

    @allure.story("Spec 5.3: Total Qty = Box Qty x Qty/Box")
    def test_total_qty(self):
        assert build([Line(3, 10, 50)]).lines[0].total_qty == 30

    @allure.story("Spec 8: Total BTP + VAT = BTP+VAT/Box x Box Qty (50 x 3 = 150)")
    def test_total_btp_vat(self):
        assert build([Line(3, 10, 50)]).lines[0].total_btp_vat == 150

    @allure.story("Spec 38/40: free qty lowers the per-piece purchase price (25*2 / 30 = 1.666..., 2.50 without free)")
    def test_free_qty_purchase_price_example(self):
        with_free = build([Line(2, 10, 25, free_qty=10)]).lines[0]
        without = build([Line(2, 10, 25)]).lines[0]
        assert with_free.purchase_price_pc == pytest.approx(50 / 30, abs=0.01)
        assert without.purchase_price_pc == pytest.approx(2.50)

    @allure.story("Spec 6: free qty adds physical stock but is not purchased quantity")
    def test_free_qty_is_physical_not_purchased(self):
        l = build([Line(10, 20, 10, free_qty=10)]).lines[0]
        assert (l.total_qty, l.physical_qty) == (200, 210)

    @allure.story("Spec 38/39: a line with Free Qty gets no discount; the discount is shared by the other lines only")
    def test_free_line_excluded_and_others_share(self):
        inv = build([Line(1, 10, 100), Line(1, 10, 300), Line(1, 10, 500, free_qty=3)], pct=10)
        assert [round(l.discount_value, 6) for l in inv.lines] == [10, 30, 0]
        assert inv.eligible_base == 400 and inv.total_discount == pytest.approx(40)

    @allure.story("Spec 39: a Flat discount is distributed proportionally to purchase price across eligible lines")
    def test_flat_discount_proportional(self):
        inv = build([Line(1, 10, 100), Line(1, 10, 300), Line(1, 10, 500, free_qty=3)], flat=80)
        assert [round(l.discount_value, 6) for l in inv.lines] == [20, 60, 0]
        assert sum(l.discount_value for l in inv.lines) == pytest.approx(80)

    @allure.story("Spec 40: Purchase Price = BTP+VAT - allocated discount, per piece")
    def test_purchase_price_after_discount(self):
        inv = build([Line(2, 10, 50)], pct=10)             # 100 - 10 = 90 over 20 pcs
        assert inv.lines[0].purchase_price_pc == pytest.approx(4.5)
        assert inv.lines[0].purchase_price_box == pytest.approx(45)

    @allure.story("Spec 41: a zero-priced line contributes 0 to the total")
    def test_zero_price_line_total_is_zero(self):
        inv = build([Line(2, 10, 0), Line(1, 10, 100)])
        assert inv.lines[0].total_btp_vat == 0 and inv.total_price == 100


@allure.epic("Inventory")
@allure.feature("Default mode - calculation model")
class TestWorkbookAnchors:
    """Numbers lifted straight from the user's workbook (cached cell values)."""

    @allure.story("Workbook 'Default Mode (2)': Test Product row (free 5, discount 10% must NOT apply)")
    def test_sheet2_test_product(self):
        inv = build([Line(10, 10, 80, free_qty=5, retail_per_box=100, wholesale_per_box=90)], pct=10)
        l = inv.lines[0]
        assert (inv.total_price, inv.total_discount, inv.final_price) == (800, 0, 800)
        assert l.purchase_price_pc == pytest.approx(7.619047619047619, abs=TOL)
        assert l.purchase_price_box == pytest.approx(76.19047619047619, abs=TOL)
        assert l.retail_margin_pct == pytest.approx(0.2380952380952381, abs=TOL)
        assert l.retail_margin_value == pytest.approx(23.80952380952381, abs=TOL)
        assert l.wholesale_margin_pct == pytest.approx(0.15343915343915346, abs=TOL)
        assert l.wholesale_margin_value == pytest.approx(13.80952380952381, abs=TOL)
        assert l.final_line_cost == pytest.approx(800, abs=TOL)

    @allure.story("Workbook 'Default Mode': three real products, no discount")
    def test_sheet1_three_products(self):
        inv = build([Line(6, 60, 633.6, retail_per_box=720, wholesale_per_box=700),
                     Line(30, 1, 171.6, retail_per_box=195, wholesale_per_box=195),
                     Line(20, 12, 369.6, retail_per_box=420, wholesale_per_box=420)])
        assert inv.total_price == pytest.approx(16341.6) and inv.total_qty == 630 and inv.total_box_qty == 56
        assert [l.purchase_price_pc for l in inv.lines] == pytest.approx([10.56, 171.6, 30.8], abs=0.01)   # sheet 1 has no rounding share
        assert [l.retail_margin_pct for l in inv.lines] == pytest.approx([0.12, 0.12, 0.12], abs=1e-3)
        assert inv.final_price == 16342          # sheet 2 rounds; sheet 1 showed 16341.6

    @allure.story("Workbook: 'Less' (M5) is deducted from the supplier Due / Advance (M3, M4)")
    def test_less_deducted_from_due(self):
        inv = build([Line(10, 10, 80)], supplier_balance=0, paid=300, less=50)          # 800 - 300 - 50
        assert (inv.due, inv.advance) == (450, 0)
        inv = build([Line(10, 10, 80)], supplier_balance=0, paid=800, less=50)
        assert (inv.due, inv.advance) == (0, 50)

    @allure.story("Workbook: supplier balance -> Due / Advance (M2..M4)")
    def test_supplier_due_and_advance(self):
        inv = build([Line(10, 10, 80)], supplier_balance=-842, paid=0)     # pharmacy holds 842 advance
        assert (inv.due, inv.advance) == (0, 42)
        inv = build([Line(10, 10, 80)], supplier_balance=0, paid=300)
        assert (inv.due, inv.advance) == (500, 0)
        inv = build([Line(10, 10, 80)], supplier_balance=0, paid=900)
        assert (inv.due, inv.advance) == (0, 100)


@allure.epic("Inventory")
@allure.feature("Default mode - calculation model")
class TestCombinationMatrix:
    """Every invariant over the whole matrix (utils.inventory_scenarios.calc_matrix)."""

    @pytest.fixture(scope="class")
    def solved(self):
        return [(cid, build(lines, pct=pct, flat=flat), pct, flat) for cid, lines, pct, flat in calc_matrix()]

    def test_matrix_size(self, solved):
        allure.attach(str(len(solved)), name="combinations evaluated")
        assert len(solved) > 2_000

    @allure.story("Free-Qty lines never receive a discount (spec 6, 38)")
    def test_free_lines_get_zero_discount(self, solved):
        bad = _fails(solved, lambda s: next((f"free line discount {l.discount_value}" for l in s[1].lines
                                             if l.free_qty > 0 and l.discount_value != 0), None))
        assert not bad, "\n".join(bad[:10])

    @allure.story("Percentage discount = pct x eligible base (spec 37-39)")
    def test_percentage_total(self, solved):
        bad = _fails([s for s in solved if s[3] == 0], lambda s: None if abs(
            s[1].total_discount - s[2] / 100 * s[1].eligible_base) < 1e-6 else
            f"{s[1].total_discount} != {s[2]}% of {s[1].eligible_base}")
        assert not bad, "\n".join(bad[:10])

    @allure.story("Flat discount total = flat amount when an eligible base exists, else 0 (spec 39)")
    def test_flat_total(self, solved):
        def chk(s):
            inv, flat = s[1], s[3]
            expect = flat if inv.eligible_base > 0 else 0
            return None if abs(inv.total_discount - expect) < 1e-6 else f"{inv.total_discount} != {expect}"
        bad = _fails([s for s in solved if s[3] > 0], chk)
        assert not bad, "\n".join(bad[:10])

    @allure.story("Sum of allocated line discounts == checkout discount; no financial discrepancy (spec 39)")
    def test_allocations_sum_to_total(self, solved):
        bad = _fails(solved, lambda s: None if abs(sum(l.discount_value for l in s[1].lines)
                                                    - s[1].total_discount) < 1e-9 else "allocation drift")
        assert not bad, "\n".join(bad[:10])

    @allure.story("All eligible lines carry the SAME discount % (allocation is proportional to price)")
    def test_equal_percentage_across_eligible_lines(self, solved):
        def chk(s):
            rates = {round(l.discount_pct, 9) for l in s[1].eligible_lines if l.total_btp_vat > 0}
            return None if len(rates) <= 1 else f"rates differ {rates}"
        bad = _fails(solved, chk)
        assert not bad, "\n".join(bad[:10])

    @allure.story("Final Price is the whole-unit rounding of Total Price - Discount (sheet K4)")
    def test_final_price_rounding(self, solved):
        def chk(s):
            inv = s[1]
            raw = inv.total_price - inv.total_discount
            ok = float(inv.final_price).is_integer() and abs(inv.final_price - raw) <= 0.5 + 1e-9
            return None if ok else f"final {inv.final_price} vs raw {raw}"
        bad = _fails(solved, chk)
        assert not bad, "\n".join(bad[:10])

    @allure.story("Spec 40: (purchase price - rounding share) x physical qty == BTP+VAT - discount")
    def test_purchase_price_formula(self, solved):
        def chk(s):
            for l in s[1].lines:
                if l.purchase_price_pc is None:
                    continue
                phys = l.total_qty + l.free_qty
                back = (l.purchase_price_pc - (l.round_adj or 0) / phys) * phys
                if abs(back - (l.total_btp_vat - l.discount_value)) > 1e-6:
                    return f"{back} != {l.total_btp_vat - l.discount_value}"
        bad = _fails(solved, chk)
        assert not bad, "\n".join(bad[:10])

    @allure.story("Sum of per-line final cost == Final Price (checkout total == sum of inventory-line costs, spec 39)")
    def test_line_costs_reconcile_with_final_price(self, solved):
        def chk(s):
            inv = s[1]
            if any(l.sheet_error for l in inv.lines):
                return None
            tot = sum((l.final_line_cost or 0) for l in inv.lines)
            return None if abs(tot - inv.final_price) < 1e-6 else f"{tot} != {inv.final_price}"
        bad = _fails(solved, chk)
        assert not bad, "\n".join(bad[:10])

    @allure.story("Raising the discount never raises Final Price")
    def test_monotonic_in_percentage(self):
        def lines():
            return [Line(2, 10, 33.3), Line(3, 12, 125.75, free_qty=5), Line(1, 1, 80)]
        prices = [build(lines(), pct=p).final_price for p in range(0, 101, 5)]
        assert prices == sorted(prices, reverse=True)


@allure.epic("Inventory")
@allure.feature("Default mode - calculation model")
class TestLargeInventories:
    """200-500 product inventories (the scale the workbook is meant to handle)."""

    @pytest.mark.parametrize("n", [200, 300, 500])
    @pytest.mark.parametrize("pct,flat", [(0, 0), (10, 0), (7.5, 0), (0, 500), (0, 12345.67)])
    @allure.story("Large inventory: totals, allocations and rounding reconcile")
    def test_large_inventory(self, n, pct, flat):
        rng = random.Random(n * 1000 + int(pct * 10) + int(flat))
        lines = _random_inventory(rng, n)
        inv = build(lines, pct=pct, flat=flat)
        assert inv.total_price == pytest.approx(sum(l.btp_vat_per_box * l.box_qty for l in lines))
        assert all(l.discount_value == 0 for l in lines if l.free_qty > 0)
        assert sum(l.discount_value for l in lines) == pytest.approx(inv.total_discount)
        if flat and inv.eligible_base > 0:
            assert inv.total_discount == pytest.approx(flat)
        if pct:
            assert inv.total_discount == pytest.approx(pct / 100 * inv.eligible_base)
        assert abs(inv.final_price - (inv.total_price - inv.total_discount)) <= 0.5 + 1e-9
        assert sum((l.final_line_cost or 0) for l in lines) == pytest.approx(inv.final_price, abs=1e-6)
        allure.attach(f"n={n} total={inv.total_price:.2f} discount={inv.total_discount:.2f} final={inv.final_price}",
                      name="inventory totals")


@allure.epic("Inventory")
@allure.feature("Default mode - calculation model")
@allure.tag("workbook-edge-case")
class TestWorkbookEdgeCases:
    """Behaviours of the workbook itself that the application must NOT inherit
    blindly. They are locked here so any change to the workbook logic is noticed,
    and each one has a matching UI test (see test_default_form / checkout)."""

    @allure.story("Sheet gap 1: a line with BTP+VAT/Box = 0 (G=0) makes Q a #VALUE! (blank W compares >= 0)")
    def test_zero_price_line_errors_in_sheet(self):
        assert build([Line(2, 10, 0)]).lines[0].sheet_error == "#VALUE!"

    @allure.story("Sheet fix (2026-10-08): a free-only line (Box Qty 0, Free > 0) now has a BLANK purchase price, not an error")
    def test_free_only_line_is_blank_in_sheet(self):
        l = build([Line(0, 10, 50, free_qty=5)]).lines[0]
        assert l.sheet_error is None and l.purchase_price_pc is None and l.final_line_cost is None

    @allure.story("Sheet guard: Qty/Box <= 0 gives a blank purchase price")
    def test_zero_qty_per_box_is_blank(self):
        l = build([Line(2, 0, 50)]).lines[0]
        assert l.purchase_price_pc is None and l.sheet_error is None

    @allure.story("Sheet gap 3: a Flat discount larger than the eligible base is not capped -> negative Final Price")
    def test_flat_larger_than_base_is_not_capped(self):
        inv = build([Line(1, 10, 100)], flat=300)
        assert inv.total_discount == 300 and inv.final_price == -200

    @allure.story("Sheet gap 4: a Flat discount with no eligible line (all free) is silently dropped")
    def test_flat_with_only_free_lines_is_dropped(self):
        inv = build([Line(1, 10, 100, free_qty=3)], flat=300)
        assert inv.total_discount == 0 and inv.final_price == 100

    @allure.story("Sheet gap 5: workbook col Q spreads 'Less' over purchased qty (D) while every other term uses D+E")
    def test_sheet_spreads_less_over_purchased_qty_only(self):
        l = build([Line(1, 10, 100, free_qty=10)], less=20, less_basis="purchased").lines[0]
        assert l.purchase_price_pc == pytest.approx(100 / 20 - 20 / 10)      # 5 - 2 (not 20/20 = 1)

    @allure.story("The application spreads 'Less' over physical qty (D+E): line costs add up to Final - Less")
    def test_app_spreads_less_over_physical_qty(self):
        inv = build([Line(1, 10, 100, free_qty=10), Line(2, 5, 40)], less=30)
        l = inv.lines[0]
        assert l.purchase_price_pc == pytest.approx((100 - 30 * 100 / 180) / 20)
        assert sum(x.final_line_cost for x in inv.lines) == pytest.approx(inv.final_price - 30, abs=0.01)


@allure.epic("Inventory")
@allure.feature("Default mode - calculation model")
@allure.tag("special-discount")
class TestSpecialDiscount:
    """Workbook column P ("Special"): a manual per-line discount VALUE.

    Sheet rules (cols N, O and I4):
      O = P                      when P > 0   (beats the % / flat share AND the free-qty exclusion)
      I4 excludes lines with P > 0 or Free > 0 (the base the % / flat share is spread over)
      flat rate = MAX(flat - SUM(P), 0) / I4   (flat is reduced by the specials first)
    The app has no Special field (not in the spec) - these lock the workbook behaviour.
    """

    @staticmethod
    def _inv(lines, **kw):
        return build(lines, **kw)

    @allure.story("Special overrides the percentage discount on its own line; others still get the %")
    def test_special_overrides_percentage(self):
        inv = self._inv([Line(1, 10, 100, special_discount=15), Line(1, 10, 200)], pct=10)
        a, b = inv.lines
        assert (a.discount_value, a.discount_pct) == (15, pytest.approx(0.15))
        assert b.discount_value == pytest.approx(20)                     # 10% of 200, base excludes line A
        assert inv.eligible_base == 200 and inv.total_discount == pytest.approx(35)
        assert inv.final_price == 265                                    # 300 - 35

    @allure.story("Special lines are removed from the eligible base (I4)")
    def test_special_excluded_from_eligible_base(self):
        inv = self._inv([Line(1, 10, 100, special_discount=15), Line(1, 10, 200), Line(1, 10, 300)], pct=10)
        assert inv.eligible_base == 500
        assert [l.discount_value for l in inv.lines] == pytest.approx([15, 20, 30])

    @allure.story("A flat discount is first reduced by the total of the specials, remainder shared by the rest")
    def test_flat_reduced_by_specials(self):
        inv = self._inv([Line(1, 10, 100, special_discount=15), Line(1, 10, 200), Line(1, 10, 300)], flat=100)
        a, b, c = inv.lines
        assert a.discount_value == 15
        assert b.discount_value == pytest.approx(34) and c.discount_value == pytest.approx(51)   # (100-15)/500 = 17%
        assert inv.total_discount == pytest.approx(100)                  # specials + remainder == flat

    @allure.story("Specials larger than the flat amount: the flat remainder is 0 and the total is the specials")
    def test_specials_exceed_flat(self):
        inv = self._inv([Line(1, 10, 100, special_discount=150), Line(1, 10, 200)], flat=100)
        assert [l.discount_value for l in inv.lines] == [150, 0]
        assert inv.total_discount == 150                                  # not capped to the flat amount

    @allure.story("Every line has a special: nothing is eligible, flat adds nothing, total = sum of specials")
    def test_all_lines_special(self):
        inv = self._inv([Line(1, 10, 100, special_discount=10), Line(1, 10, 200, special_discount=25)], flat=500)
        assert inv.eligible_base == 0 and inv.total_discount == 35 and inv.final_price == 265

    @allure.story("Special beats the free-qty exclusion: a free line WITH a special is discounted by that value")
    def test_special_on_free_line(self):
        inv = self._inv([Line(1, 10, 100, free_qty=5, special_discount=20), Line(1, 10, 100)], pct=10)
        free_line, plain = inv.lines
        assert free_line.discount_value == 20 and plain.discount_value == pytest.approx(10)
        assert inv.eligible_base == 100                                   # free line is out of the base either way
        # per-piece cost spreads over purchased + free pieces: (100 - 20) / 15
        assert free_line.purchase_price_pc == pytest.approx(80 / 15, abs=0.01)

    @pytest.mark.parametrize("special", [0, -5])
    @allure.story("A zero or negative special is NOT a special: the line is treated as a normal eligible line")
    def test_non_positive_special_ignored(self, special):
        inv = self._inv([Line(1, 10, 100, special_discount=special), Line(1, 10, 100)], pct=10)
        assert [l.discount_value for l in inv.lines] == pytest.approx([10, 10]) and inv.eligible_base == 200

    @allure.story("Special larger than the line total is not capped (negative line cost) - sheet gap")
    def test_special_larger_than_line_total(self):
        inv = self._inv([Line(1, 10, 100, special_discount=150)])
        l = inv.lines[0]
        assert l.discount_value == 150 and l.discount_pct == pytest.approx(1.5)
        assert inv.final_price == -50 and l.purchase_price_pc < 0

    @allure.story("Special on a zero-priced line: value kept, percentage reported as 0 (N guards G>0)")
    def test_special_on_zero_priced_line(self):
        inv = self._inv([Line(2, 10, 0, special_discount=5), Line(1, 10, 100)])
        z = inv.lines[0]
        assert z.discount_value == 5 and z.discount_pct == 0

    @allure.story("Per-piece purchase price of a special line = (BTP+VAT - special) / (Qty + Free)")
    def test_special_purchase_price(self):
        inv = self._inv([Line(2, 10, 50, special_discount=10)])           # (100 - 10) / 20 = 4.5, final 90 whole
        l = inv.lines[0]
        assert l.purchase_price_pc == pytest.approx(4.5) and l.purchase_price_box == pytest.approx(45)

    @allure.story("Special is reflected in Final Price rounding and the Due / Advance figures")
    def test_special_with_rounding_and_due(self):
        inv = self._inv([Line(1, 10, 33.3, special_discount=0.4)], paid=0)      # 33.3 - 0.4 = 32.9 -> 33
        assert inv.final_price == 33 and inv.round_adjustment == pytest.approx(0.1)
        assert inv.due == 33

    @pytest.mark.parametrize("pct,flat", [(0, 0), (10, 0), (7.5, 0), (0, 250), (0, 99999)])
    @allure.story("Matrix with specials: total discount = sum(specials) + the share of the rest")
    def test_total_discount_formula(self, pct, flat):
        rng = random.Random(42 + int(pct * 10) + flat)
        lines = _random_inventory(rng, 60, free_ratio=0.2)
        for l in lines:
            if rng.random() < 0.15:
                l.special_discount = round(rng.uniform(1, 40), 2)
        inv = build(lines, pct=pct, flat=flat)
        specials = sum(l.special_discount for l in lines if l.special_discount > 0)
        base = sum(l.total_btp_vat for l in lines if l.free_qty <= 0 and l.special_discount <= 0)
        share = (max(flat - specials, 0) if base > 0 else 0) if flat else pct / 100 * base
        assert inv.total_discount == pytest.approx(specials + share, abs=1e-6)
        if flat and base > 0:
            assert inv.total_discount == pytest.approx(max(flat, specials), abs=1e-6)

    @pytest.mark.parametrize("n", [200, 300, 500])
    @allure.story("200-500 products with specials: line costs still reconcile to Final Price")
    def test_large_inventory_with_specials(self, n):
        rng = random.Random(n)
        lines = _random_inventory(rng, n, free_ratio=0.2)
        for l in lines:
            if rng.random() < 0.1:
                l.special_discount = round(rng.uniform(1, 40), 2)
        inv = build(lines, pct=8, flat=0)
        assert all(l.discount_value == l.special_discount for l in lines if l.special_discount > 0)
        assert abs(inv.final_price - (inv.total_price - inv.total_discount)) <= 0.5 + 1e-9
        if not any(l.sheet_error for l in lines):
            assert sum((l.final_line_cost or 0) for l in lines) == pytest.approx(inv.final_price, abs=1e-6)


@allure.epic("Inventory")
@allure.feature("Default mode - calculation model")
@allure.tag("round-off")
class TestRoundOffAllocation:
    """Round Off (Final Price rounding) is shared between lines in proportion to each line's
    AFTER-discount amount - the application's rule, confirmed correct by the user (2026-10-08).
    The workbook's col X shares it by PRE-discount BTP+VAT instead; both reconcile to Final Price and
    differ only when some lines are discounted and others are not."""

    @staticmethod
    def _mixed():
        # A: 100.00, eligible for the 10 %. B: 100.60 with 10 free pcs -> no discount.
        return [Line(1, 10, 100.00, name="A"), Line(1, 10, 100.60, free_qty=10, name="B")]

    @allure.story("Worked example: 10 % on A only -> Round Off +0.40 shared by after-discount amounts")
    def test_worked_example_post_discount(self):
        inv = build(self._mixed(), pct=10)
        a, b = inv.lines
        assert (inv.total_price, inv.total_discount, inv.final_price) == (pytest.approx(200.60), pytest.approx(10), 191)
        assert inv.round_adjustment == pytest.approx(0.40)
        assert a.round_adj == pytest.approx(0.40 * 90.00 / 190.60)        # 0.18888
        assert b.round_adj == pytest.approx(0.40 * 100.60 / 190.60)       # 0.21112
        assert a.final_line_cost == pytest.approx(90.188877, abs=1e-5)
        assert b.final_line_cost == pytest.approx(100.811122, abs=1e-5)
        assert a.final_line_cost + b.final_line_cost == pytest.approx(191)
        assert a.purchase_price_pc == pytest.approx(9.0189, abs=1e-4)
        assert b.purchase_price_pc == pytest.approx(5.0406, abs=1e-4)      # 100.811122 / 20 pcs (free included)

    @allure.story("The workbook's own col X rule (pre-discount) gives a different split for the same cart")
    def test_worked_example_sheet_rule_differs(self):
        inv = build(self._mixed(), pct=10, round_basis="pre_discount")
        a, b = inv.lines
        assert a.final_line_cost == pytest.approx(90.199402, abs=1e-5)
        assert b.final_line_cost == pytest.approx(100.800598, abs=1e-5)
        assert a.final_line_cost + b.final_line_cost == pytest.approx(191)

    @allure.story("Real journey two_one_free-flat50: Final 16.52 / 64.48 (matches what the app displays)")
    def test_real_journey_values(self):
        inv = build([Line(1, 10, 66.6, name="TEST PRODUCT"), Line(1, 10, 64.8, free_qty=10, name="100%")], flat=50)
        a, b = inv.lines
        assert inv.final_price == 81 and inv.round_adjustment == pytest.approx(-0.40)
        assert a.final_line_cost == pytest.approx(16.518, abs=0.005) and round(a.final_line_cost, 2) == 16.52
        assert b.final_line_cost == pytest.approx(64.482, abs=0.005) and round(b.final_line_cost, 2) == 64.48

    @allure.story("When every line gets the same discount %, both rules give the same split")
    def test_rules_agree_when_uniform(self):
        for pct in (0, 10, 7.5):
            lines = lambda: [Line(2, 10, 33.3), Line(3, 12, 125.75), Line(1, 1, 80.35)]
            post = build(lines(), pct=pct)
            pre = build(lines(), pct=pct, round_basis="pre_discount")
            assert [l.round_adj for l in post.lines] == pytest.approx([l.round_adj for l in pre.lines])

    @pytest.mark.parametrize("pct,flat", [(0, 0), (10, 0), (7.5, 0), (0, 50), (0, 777.77), (33.333, 0)])
    @allure.story("Shares of Round Off always add up to the Round Off and line costs add up to Final Price")
    def test_allocation_reconciles(self, pct, flat):
        rng = random.Random(int(pct * 10) + int(flat))
        for n in (3, 60, 500):
            lines = _random_inventory(rng, n, free_ratio=0.25)
            inv = build(lines, pct=pct, flat=flat)
            shares = [l.round_adj for l in lines if l.round_adj is not None]
            assert sum(shares) == pytest.approx(inv.round_adjustment, abs=1e-6)
            if not any(l.sheet_error for l in lines):
                assert sum((l.final_line_cost or 0) for l in lines) == pytest.approx(inv.final_price, abs=1e-6)

    @allure.story("A free-qty (undiscounted) line takes a larger share of the Round Off than a discounted line of the same price")
    def test_discounted_line_takes_smaller_share(self):
        inv = build([Line(1, 10, 100, name="disc"), Line(1, 10, 100.6, free_qty=1, name="free")], pct=10)
        disc, free = inv.lines
        assert abs(free.round_adj) > abs(disc.round_adj) > 0
