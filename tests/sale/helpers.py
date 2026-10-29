"""Shared set-up steps for the Sale tests: put a real walk-in (or registered-customer) sale into Sale Record."""
from __future__ import annotations

from tests.sale.conftest import PRODUCT, PRODUCT_2

PRICE = 50


def term(name: str) -> str:
    return name.lower()


def sell(sale, checkout, qty: int = 1, price=PRICE, product: str = PRODUCT, customer: str | None = None, paid=None) -> None:
    """One line, optional registered customer and paid amount; the sale must complete (shortfall/excess dialogs are not handled)."""
    sale.open()
    sale.add_line(term(product), qty, price=price, named=product)
    sale.go_to_checkout()
    if customer:
        checkout.choose_customer(customer)
    if paid is not None:
        checkout.set_paid(paid)
    status, body = checkout.complete_once()
    assert status is not None and status < 300, f"set-up sale failed: {status} {body[:200]}"


def sell_two_lines(sale, checkout, discount_tk=None) -> None:
    """Item A = PRODUCT 2 x 100, item B = PRODUCT_2 1 x 300 (the SRS 7.2 example), optional overall discount in Tk."""
    sale.open()
    sale.add_line(term(PRODUCT), 2, price=100, named=PRODUCT)
    sale.add_line(term(PRODUCT_2), 1, price=300, named=PRODUCT_2)
    sale.go_to_checkout()
    if discount_tk:
        checkout.set_overall_discount(discount_tk, unit="Tk")
    status, body = checkout.complete_once()
    assert status is not None and status < 300, f"set-up sale failed: {status} {body[:200]}"
