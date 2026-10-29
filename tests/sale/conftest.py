"""Fixtures for the Sale suite (POS, checkout, cashier, Sale Record).

Runs in Manik Pharma like the Inventory suites and reuses their shared browser session (one login, one pharmacy selection).
The sales it completes are real: they change stock, treasury and Sale Record, so use a pharmacy that may receive test sales.
Sale Config / Loyalty Config fixtures (``sale_config``, ``default_config``, ``loyalty_config``) live in tests/settings/conftest.py.

Optional environment overrides (defaults match Manik Pharma):
    QA_SALE_PRODUCT    product sold by the tests            (default "TEST PRODUCT", stocked, sale price typed per test)
    QA_SALE_PRODUCT_2  a second stocked product             (default "3-C", sale price 35)
    QA_EXPIRED_PRODUCT a product whose only stock is expired (default "3-C": batch expiry 1 Jan 1970)
"""
from __future__ import annotations

import os

import pytest

from pages.cashier_page import CashierPage
from pages.customer_page import CustomerPage
from pages.sale_checkout_page import SaleCheckoutPage
from pages.sale_page import SalePage
from pages.sale_record_page import SaleRecordPage
from pages.sale_return_page import SaleReturnPage
from tests.inventory.default_mode.conftest import (  # noqa: F401
    context, page, pharmacy, run_tag)
from tests.settings.conftest import default_config, loyalty_config, sale_config  # noqa: F401

PRODUCT = os.getenv("QA_SALE_PRODUCT", "TEST PRODUCT")
PRODUCT_2 = os.getenv("QA_SALE_PRODUCT_2", "3-C")
PRODUCT_2_PRICE = 35
EXPIRED_PRODUCT = os.getenv("QA_EXPIRED_PRODUCT", "3-C")


@pytest.fixture()
def sale(page, pharmacy, default_config) -> SalePage:
    """The POS with an empty cart. ``default_config`` is requested first: it navigates to Settings to reset the config,
    which would otherwise leave the browser off the POS after this fixture had opened it."""
    return SalePage(page).open()


@pytest.fixture()
def checkout(page) -> SaleCheckoutPage:
    return SaleCheckoutPage(page)


@pytest.fixture()
def cashier(page, pharmacy) -> CashierPage:
    return CashierPage(page)


@pytest.fixture()
def sale_record(page, pharmacy) -> SaleRecordPage:
    return SaleRecordPage(page)


@pytest.fixture()
def customers(page, pharmacy) -> CustomerPage:
    return CustomerPage(page)


@pytest.fixture()
def sale_return(page, pharmacy) -> SaleReturnPage:
    return SaleReturnPage(page)
