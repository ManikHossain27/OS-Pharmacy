"""Checkout behaviour that is identical in every inventory mode (spec sections 35-41, 44.1).

A mode's ``TestCheckoutBehaviour`` inherits :class:`CheckoutBehaviourCases` and supplies

* ``MODE``   - the mode name the Inventory page reports,
* ``SHAPES`` - the mode's ``CART_SHAPES``,
* ``build``  - the mode's calculation oracle (``build(lines, pct=..., flat=...)``),
* ``SUMMARY_LABELS`` / ``_totals`` - only when the mode's checkout summary differs from the common one.

It adds only the tests that are specific to the mode.  The class is not named ``Test*`` so pytest collects the cases
once per mode, under that mode's class.
"""
from __future__ import annotations

import allure
import pytest

from utils.inventory_scenarios import Scenario


class CheckoutBehaviourCases:
    MODE: str
    SHAPES: dict
    build = None            # staticmethod(<mode oracle>) in the subclass
    SUMMARY_LABELS = ("Total Price (TP+VAT)", "General Discount", "Special Discount", "Round Off", "Final Price",
                      "Total Paid", "Due")

    # ------------------------------------------------------------------ helpers
    def _open(self, flow, shape="two_one_free", discount=None):
        j = flow.fill_cart(Scenario(shape, self.SHAPES[shape], discount=discount))
        return j, flow.open_checkout(j)

    @staticmethod
    def _totals(co) -> dict:
        """The checkout summary as a dict (TP/VAT mode reads its richer summary)."""
        return co.summary()

    # ------------------------------------------------------------------ totals and discount
    @allure.story("Total Price equals the cart total (spec 36)")
    @pytest.mark.smoke
    def test_total_matches_cart(self, flow):
        j = flow.fill_cart(Scenario("t", self.SHAPES["two_plain"]))
        cart_total = flow.inventory.cart_total_price()
        co = flow.open_checkout(j)
        assert self._totals(co)["total_price"] == pytest.approx(cart_total)

    @pytest.mark.parametrize("pct", [0, 1, 5, 10, 12.5, 33.333, 50, 99, 100])
    @allure.story("A % discount applies to the eligible lines only - never to free-qty lines (spec 37-39)")
    def test_percentage_excludes_free(self, flow, pct):
        j, co = self._open(flow, "three_plain_free_plain")
        co.set_discount(pct, "%")
        o = self.build(j.lines, pct=pct)
        totals = self._totals(co)
        assert totals["discount_amount"] == pytest.approx(o.total_discount, abs=0.011),             f"discount {totals['discount_amount']} should be {pct}% of the eligible base (BUG-INV-001 if it includes Free-Qty lines)"
        self._check_percentage_side_effects(o, totals)

    def _check_percentage_side_effects(self, oracle, totals) -> None:
        """Mode-specific values a percentage discount must leave alone (TP/VAT: VAT)."""

    @pytest.mark.parametrize("flat", [1, 50, 200, 777.77])
    @allure.story("A Flat discount is distributed over eligible lines; total discount == flat (spec 39)")
    def test_flat_discount_total(self, flow, flat):
        j, co = self._open(flow, "three_plain_free_plain")
        co.set_discount(flat, "Tk")
        assert self._totals(co)["discount_amount"] == pytest.approx(self.build(j.lines, flat=flat).total_discount, abs=0.011)

    @allure.story("Removing the discount restores Final Price = Total Price")
    def test_clear_discount_restores_total(self, flow):
        j, co = self._open(flow, "two_plain", (10, "%"))
        co.set_discount(0, "%")
        s = co.summary()
        assert s["final_price"] == pytest.approx(s["total_price"], abs=0.51)

    @allure.story("Switching discount type recalculates (% -> Tk -> %)")
    def test_switch_discount_type(self, flow):
        j, co = self._open(flow, "two_plain")
        amounts = []
        for value, kind in ((10, "%"), (40, "Tk"), (10, "%")):
            co.set_discount(value, kind)
            amounts.append(co.summary()["discount_amount"])
        pct, flat, pct_again = amounts
        assert pct == pytest.approx(self.build(j.lines, pct=10).total_discount, abs=0.011)
        assert flat == pytest.approx(40, abs=0.011) and pct_again == pytest.approx(pct, abs=0.011)

    @allure.story("Discount input is disabled when every line has Free Qty - nothing is eligible (spec 38)")
    def test_all_free_cart_discount_disabled(self, flow):
        j, co = self._open(flow, "all_free")
        assert not co.discount_enabled(), "discount input must be disabled when no line is eligible"
        assert co.summary()["discount_amount"] == pytest.approx(0, abs=0.011)

    @pytest.mark.parametrize("pct", [-5, 101, 1000])
    @allure.story("Out-of-range percentage must not produce a negative Final Price")
    @pytest.mark.negative
    def test_percentage_out_of_range(self, flow, pct):
        j, co = self._open(flow, "two_plain")
        co.set_discount(pct, "%")
        s = co.summary()
        assert s["final_price"] >= 0 and s["discount_amount"] <= s["total_price"] + 0.011, f"out-of-range {pct}% accepted: {s}"

    @allure.story("Workbook gap: a Flat discount larger than the eligible total must not give a negative Final Price")
    @pytest.mark.negative
    def test_flat_larger_than_total(self, flow):
        j, co = self._open(flow, "single_plain")
        co.set_discount(10_000_000, "Tk")
        s = co.summary()
        assert s["final_price"] >= 0, f"flat discount > total produced Final Price {s['final_price']} (the sheet has no cap)"

    # ------------------------------------------------------------------ summary and payment
    @allure.story("The checkout summary shows every pricing line")
    def test_summary_lines_present(self, flow):
        j, co = self._open(flow, "two_plain")
        for label in self.SUMMARY_LABELS:
            assert co.summary_root.get_by_text(label, exact=True).count() == 1, f"summary line {label!r} missing"

    @allure.story("Total Paid is pre-filled with the Final Price and Due is 0")
    def test_paid_prefilled_with_final_price(self, flow):
        j, co = self._open(flow, "two_plain")
        s = co.summary()
        assert s["total_paid"] == pytest.approx(s["final_price"], abs=0.011) and s["due"] == pytest.approx(0, abs=0.011)

    @pytest.mark.parametrize("ratio", [pytest.param(0.0, id="zero"), pytest.param(0.5, id="half"),
                                       pytest.param(1.0, id="full")])
    @allure.story("Paid amount drives Due = Final Price - Paid (spec 44.1)")
    def test_paid_amount_due(self, flow, ratio):
        j, co = self._open(flow, "two_plain")
        o = flow.oracle(j)
        flow.pay(co, j, 0)
        due_unpaid = co.summary()["due"]          # = max(Final Price + supplier balance, 0): the supplier may hold an advance
        paid = round(o.final_price * ratio, 2)
        flow.pay(co, j, paid)
        s = co.summary()
        assert s["total_paid"] == pytest.approx(paid, abs=0.011)
        assert s["due"] == pytest.approx(max(due_unpaid - paid, 0), abs=0.51), \
            f"Due {s['due']} != unpaid Due {due_unpaid} - paid {paid}"
        assert due_unpaid <= o.final_price + 0.51, "Due can only be reduced, never raised, by the supplier balance here"

    @allure.story("Overpayment is shown as Advance (not a negative Due) with the excess amount (spec 44.1)")
    @allure.issue("BUG-INV-016")
    @pytest.mark.negative
    def test_overpayment_shown_as_advance(self, flow):
        j, co = self._open(flow, "two_plain")
        flow.pay(co, j, flow.oracle(j).final_price + 100)
        s = co.summary()
        assert co.advance_label_shown(), "overpayment not displayed as Advance"
        assert s["advance"] == pytest.approx(100, abs=0.51) and s["due"] == 0

    @allure.story("Edit Cart returns to the same mode's Inventory page with the cart intact (spec 35)")
    def test_edit_cart_keeps_items(self, flow):
        j, co = self._open(flow, "two_plain")
        inv = co.edit_cart()
        assert inv.total_items() == 2 and inv.current_mode() == self.MODE
