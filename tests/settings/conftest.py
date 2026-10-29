"""Fixtures for the Settings suites (Sale Config, Loyalty Config).

Both configurations are per pharmacy and shared by every user of it, so each fixture snapshots the stored values first and puts
them back after the test, whatever the test changed. Runs in Manik Pharma on the Inventory suites' shared browser session.
The Sale suite imports ``sale_config`` / ``default_config`` from here (tests/sale/conftest.py).
"""
from __future__ import annotations

import pytest

from pages.settings.loyalty_config_page import LoyaltyConfigPage
from pages.settings.sale_config_page import SaleConfigPage
from tests.inventory.default_mode.conftest import (  # noqa: F401
    context, page, pharmacy, run_tag)


@pytest.fixture()
def sale_config(page, pharmacy):
    """The Sale Config page. The persisted switches are put back after the test, whatever it changed."""
    cfg = SaleConfigPage(page).open()
    original = cfg.state()
    yield cfg
    try:
        now = SaleConfigPage(page).open()
        if now.state() != original:
            now.set_state(original)
            now.save()
    except Exception:
        pass


@pytest.fixture()
def default_config(sale_config):
    """Sale Config with every toggle OFF and Retail (the pharmacy's defaults), restored by ``sale_config``."""
    sale_config.apply({"outOfStockSale": False, "allowLossSale": False, "stockQty": False, "companyName": False,
                       "profitMargin": False, "rackNo": False, "separateCashier": False, "retail": True})
    return sale_config


@pytest.fixture()
def loyalty_config(page, pharmacy):
    """The Loyalty Config page. The four stored numbers are put back after the test, whatever it saved."""
    cfg = LoyaltyConfigPage(page).open()
    original = cfg.values()
    yield cfg
    try:
        now = LoyaltyConfigPage(page).open()
        if now.values() != original:
            now.set(**original)
            now.save()
    except Exception:
        pass
