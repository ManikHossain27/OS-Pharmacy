"""Fixtures for the Default-mode suite."""
from __future__ import annotations

import os
import time
from typing import Iterator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from config import settings
from conftest import ensure_pharmacy
from utils import auth

from pages.inventory_flow import InventoryFlow
from pages.inventory_page import InventoryPage


@pytest.fixture(scope="session")
def run_tag() -> str:
    return time.strftime("%m%d%H%M%S")


@pytest.fixture()
def catalogue(inventory_data) -> list[str]:
    """Products for P0/P1/P2. Verified live 2026-10-06: the dropdown search for each returns
    that product first (inventory_data.json's '3 products only' note is stale - the pharmacy
    now has the full catalogue). '3 BION' is also a row in the user's workbook."""
    if os.getenv("QA_PRODUCTS"):          # a pharmacy without the TEST PRODUCT custom product: "a,b,c"
        return [p.strip() for p in os.getenv("QA_PRODUCTS").split(",")]
    return list(inventory_data.get("default_mode_products", ["TEST PRODUCT", "100%", "3 BION"]))


@pytest.fixture()
def default_inventory(page, pharmacy, catalogue) -> InventoryPage:
    """Default-mode Inventory page with an EMPTY cart and product references wired."""
    inv = InventoryPage(page)
    if not inv.soft_reset():
        inv.open("Default")
    InventoryPage.product_catalogue = catalogue
    if inv.cart_row_count():
        inv.clear_cart()
    return inv


@pytest.fixture()
def flow(default_inventory, run_tag) -> InventoryFlow:
    return InventoryFlow(default_inventory, run_tag)


# --------------------------------------------------------------------------
# Shared browser session for this suite.
#
# The staging portal is a Vite DEV build: a cold page load fetches ~120 modules
# (~40 s), and the default per-test context pays that on EVERY test (~4 min per
# test). Here one authenticated context/page and one pharmacy selection are
# reused for the whole run, so the dev build loads once; every test still
# starts from a clean state because `default_inventory` re-navigates to the
# inventory route and empties the server-side cart.
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def context(browser: Browser, storage_state_path) -> Iterator[BrowserContext]:
    ctx = browser.new_context(base_url=settings.base_url, storage_state=str(storage_state_path),
                              viewport={"width": 1920, "height": 1000})
    ctx.set_default_timeout(settings.default_timeout)
    tracing = os.getenv("PW_TRACE", "").lower() in {"1", "true", "yes", "on"}
    if tracing:   # opt-in: PW_TRACE=1 -> reports/traces/default_mode.zip  (open with: playwright show-trace <zip>)
        ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield ctx
    if tracing:
        out = settings.reports_dir / "traces"
        out.mkdir(parents=True, exist_ok=True)
        ctx.tracing.stop(path=str(out / "default_mode.zip"))
    ctx.close()


@pytest.fixture(scope="session")
def page(context: BrowserContext) -> Iterator[Page]:
    pg = context.new_page()
    errors: list[str] = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))
    pg._qa_console_errors = errors  # type: ignore[attr-defined]
    yield pg
    pg.close()


@pytest.fixture(scope="session")
def pharmacy(page: Page, storage_state_path):
    """Select Manik Pharma once. A stale reused session shows up on staging as a truncated
    pharmacy picker (BUG-API-001) rather than a /login redirect, so on that skip: log in
    again, refresh the saved state and retry once before giving up. The state is re-saved
    AFTER the pharmacy is selected so the next run starts already inside Manik Pharma and
    skips the picker (each page load costs ~40-60 s on the staging dev build)."""
    try:
        selected = ensure_pharmacy(page, storage_state_path)
    except pytest.skip.Exception:
        page.context.clear_cookies()
        page.goto(settings.base_url + "login", wait_until="domcontentloaded")
        auth.login(page, storage_state_path)
        selected = ensure_pharmacy(page, storage_state_path)
    try:
        page.context.storage_state(path=str(storage_state_path))
    except Exception:
        pass
    return selected
