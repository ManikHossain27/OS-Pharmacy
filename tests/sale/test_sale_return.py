"""Sale Return (SRS 7.2): proportional refund, full return, quantity limits, cancelled sales, rounding.

Each test sells first (real sales of 1-3 pieces) and then returns from the top Sale Record row. Tests assert the CORRECT
behaviour; the ones that fail today carry ``allure.issue``.
"""
from __future__ import annotations

import allure
import pytest

from tests.sale.helpers import sell, sell_two_lines

pytestmark = [pytest.mark.sale, pytest.mark.regression]


def _open_return(sale_record, sale_return):
    return sale_return.open_from_record(sale_record.open(), 0)


@allure.epic("Sale")
@allure.feature("Sale Return")
class TestSaleReturn:

    @allure.story("TC-SALE-RT-03: refund = the item's net realised price (SRS 7.2 example: 90, not 100)")
    def test_refund_follows_proportional_net_price(self, sale, checkout, sale_record, sale_return, default_config):
        sell_two_lines(sale, checkout, discount_tk=50)               # A 2 x 100, B 1 x 300, overall Tk 50 -> paid 450
        _open_return(sale_record, sale_return)
        sale_return.set_return_qty(0, 1)
        assert sale_return.refund_preview() == pytest.approx(90.0), "returning 1 pc of item A must refund Tk 90"

    @allure.story("TC-SALE-RT-04: a full return refunds exactly what was paid")
    def test_full_return_refunds_amount_paid(self, sale, checkout, sale_record, sale_return, default_config):
        sell(sale, checkout, qty=2)                                  # Tk 100
        _open_return(sale_record, sale_return)
        sale_return.set_return_qty(0, 2)
        assert sale_return.refund_preview() == pytest.approx(100.0)
        sale_return.go_to_return_checkout()
        status, body = sale_return.complete_once()
        assert status is not None and status < 300, f"return failed: {status} {body[:200]}"

    @allure.story("TC-SALE-RT-06: the server refuses a return above what is left on the line")
    def test_return_beyond_remaining_is_refused(self, sale, checkout, sale_record, sale_return, default_config):
        sell(sale, checkout, qty=2)
        _open_return(sale_record, sale_return)
        sale_return.set_return_qty(0, 1).go_to_return_checkout()
        status, _ = sale_return.complete_once()
        assert status is not None and status < 300, "set-up: the first return of 1 pc should succeed"
        _open_return(sale_record, sale_return)
        sale_return.set_return_qty(0, 2)
        if not sale_return.page.get_by_role("button", name="Go to Return Checkout").is_enabled():
            return                                                   # the form itself refuses the quantity
        sale_return.go_to_return_checkout()
        status, body = sale_return.complete_once()
        assert status is None or status >= 400, f"2 pcs returned although 1 was left: {status} {body[:200]}"

    @allure.story("BUG-SALE-020: invalid return quantities (-1, 0.5, text) are rejected with a message")
    @allure.issue("BUG-SALE-020")
    def test_invalid_return_quantities_are_rejected(self, sale, checkout, sale_record, sale_return, default_config):
        sell(sale, checkout, qty=2)
        _open_return(sale_record, sale_return)
        problems = []
        for value in ("-1", "0.5", "abc"):
            sale_return.set_return_qty(0, value)
            refund = sale_return.refund_preview()
            message = sale_return.validation_text()
            if refund not in (0.0,) and not message:
                problems.append(f"{value!r}: refund preview Tk {refund}, no message, box shows {sale_return.qty_value(0)!r}")
            elif value == "abc" and sale_return.qty_value(0) == "abc" and not message:
                problems.append(f"{value!r}: text kept in the box with no message")
        assert not problems, "invalid quantities accepted: " + "; ".join(problems)

    @allure.story("BUG-SALE-019: a cancelled sale cannot be returned")
    @allure.issue("BUG-SALE-019")
    def test_cancelled_sale_cannot_be_returned(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout, qty=1)
        sale_record.open()
        toast = sale_record.cancel_row(0)
        assert "cancel" in toast.lower(), f"set-up: cancel failed ({toast!r})"
        sale_record.open()
        assert sale_record.top_row().status == "Cancelled"
        assert not sale_record.action_enabled(0, "Return Sale"), "Return Sale is offered for a cancelled sale"

    @allure.story("BUG-SALE-038: a one-piece return refunds the exact per-piece value, not a rounded-up amount")
    @allure.issue("BUG-SALE-038")
    def test_single_piece_refund_is_not_rounded_up(self, sale, checkout, sale_record, sale_return, default_config):
        sell(sale, checkout, qty=2, price=50.5)                      # Tk 101 -> Tk 50.50 per piece
        _open_return(sale_record, sale_return)
        sale_return.set_return_qty(0, 1).go_to_return_checkout()
        figures = sale_return.checkout_figures()
        assert figures["Return to Customer"] == pytest.approx(figures["Return Price"]), (
            f"Return Price Tk {figures['Return Price']} but Return to Customer Tk {figures['Return to Customer']}")
