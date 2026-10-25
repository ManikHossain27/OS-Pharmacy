"""Fixtures for the Inventory Config suite (Settings > Inventory Config: VAT % and Opening Stock %).

The configuration is per pharmacy and the tests change it, so run them in a pharmacy of their own (QA Ret Pharma A, no Cash
balance: purchases are bought on credit) and every test puts the defaults (17.4 / 12) back afterwards.
"""
from __future__ import annotations

import pytest

from pages.inventory_config_page import InventoryConfigPage
from tests.inventory.default_mode.conftest import (  # noqa: F401
    catalogue, context, default_inventory, flow, page, pharmacy, run_tag)
from tests.inventory.edit_module.conftest import (  # noqa: F401
    Saved, create, create_in, create_inventory, mode, mode_saved, record, saved)
from tests.inventory.opening_stock_mode.conftest import opening_inventory  # noqa: F401
from tests.inventory.tp_vat_mode.conftest import tpvat_inventory  # noqa: F401

DEFAULT_VAT = 17.4
DEFAULT_OPENING = 12.0


def set_config(page, vat=None, opening=None) -> InventoryConfigPage:
    """Open Inventory Config, save the given values and return the page object (asserts the save succeeded)."""
    cfg = InventoryConfigPage(page).open()
    status, body, toast = cfg.save_values(vat, opening)
    assert status is not None and status < 300, f"saving VAT={vat} opening={opening} failed: {status} {body[:200]} {toast}"
    return cfg


@pytest.fixture()
def cfg(page, pharmacy) -> InventoryConfigPage:
    """The Inventory Config page, with the defaults put back after the test."""
    yield InventoryConfigPage(page).open()
    try:
        now = InventoryConfigPage(page).open()
        if now.numbers() != (DEFAULT_VAT, DEFAULT_OPENING):
            now.save_values(DEFAULT_VAT, DEFAULT_OPENING)
    except Exception:
        pass


@pytest.fixture()
def restore(page, pharmacy):
    """Put the defaults back after a test that changes the configuration without using ``cfg``."""
    yield
    try:
        now = InventoryConfigPage(page).open()
        if now.numbers() != (DEFAULT_VAT, DEFAULT_OPENING):
            now.save_values(DEFAULT_VAT, DEFAULT_OPENING)
    except Exception:
        pass
