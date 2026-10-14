"""Fixtures for the Inventory Record list suite (spec section 43).

Browser session / pharmacy fixtures are the Default-mode suite's (one authenticated session for the whole run).
The suite is READ-ONLY: it never creates inventory.
"""
from __future__ import annotations

from datetime import date

import pytest

from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.default_mode.conftest import catalogue, context, page, pharmacy, run_tag  # noqa: F401


@pytest.fixture()
def record(page, pharmacy) -> InventoryRecordPage:
    """Inventory Record list, freshly opened (no filter, first page)."""
    rec = InventoryRecordPage(page).open()
    # filters / search survive navigation inside the session - start every test from a clean list
    rec.reset_filters_btn.click()
    page.wait_for_timeout(1500)
    return rec.wait_loaded()


@pytest.fixture()
def record_all(record) -> InventoryRecordPage:
    """Inventory Record list over the whole of this year - the default scope is only 'today', which is often empty."""
    record.set_date_range(f"{date.today().year}-01-01", date.today().isoformat())
    return record
