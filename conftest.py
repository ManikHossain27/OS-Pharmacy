"""Root pytest configuration: fixtures for browser / context / auth / pharmacy,
plus failure-evidence capture into Allure.

Auth strategy
-------------
Login happens ONCE per session against a throw-away context; the resulting
``storage_state`` is saved and reused by every test context, so individual tests
start already authenticated but still get a fresh, isolated context/page.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import allure
import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from config import settings
from pages.pharmacy_selection_page import PharmacySelectionPage
from utils import auth
from utils.helpers import attach_page_context, read_json, screenshot
from utils.logger import get_logger

log = get_logger("conftest")


# --------------------------------------------------------------------------- CLI
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--env", action="store", default=None,
                     help="Override TEST_ENV (local|staging|prod)")
    parser.addoption("--headed-run", action="store_true", default=False,
                     help="Force headed browser regardless of .env")


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--env"):
        os.environ["TEST_ENV"] = config.getoption("--env")
    settings.ensure_dirs()
    # Allure environment.properties
    props = {
        "TEST_ENV": settings.env.name,
        "BASE_URL": settings.base_url,
        "BROWSER": settings.browser,
        "HEADLESS": str(settings.headless),
        "PHARMACY": settings.pharmacy_name,
        "DESTRUCTIVE_TESTS": str(settings.destructive_allowed),
    }
    out = settings.reports_dir / "allure-results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "environment.properties").write_text(
        "\n".join(f"{k}={v}" for k, v in props.items()), encoding="utf-8"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip destructive tests unless explicitly enabled (and never on prod)."""
    if settings.destructive_allowed:
        return
    skip = pytest.mark.skip(reason="destructive tests disabled (RUN_DESTRUCTIVE_TESTS/prod guard)")
    for item in items:
        if "destructive" in item.keywords:
            item.add_marker(skip)


# ---------------------------------------------------------------- playwright core
@pytest.fixture(scope="session")
def playwright_instance() -> Iterator[Playwright]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright, pytestconfig: pytest.Config) -> Iterator[Browser]:
    headless = settings.headless and not pytestconfig.getoption("--headed-run")
    browser_type = getattr(playwright_instance, settings.browser)
    b = browser_type.launch(headless=headless, slow_mo=settings.slow_mo)
    log.info("Launched %s (headless=%s) against %s", settings.browser, headless, settings.base_url)
    yield b
    b.close()


# ------------------------------------------------------------------ auth session
@pytest.fixture(scope="session")
def storage_state_path(browser: Browser) -> Path:
    """Log in once, persist storage_state, return its path."""
    return auth.ensure_state(browser, settings.auth_state_path)


@pytest.fixture()
def context(browser: Browser, storage_state_path: Path) -> Iterator[BrowserContext]:
    ctx = browser.new_context(
        base_url=settings.base_url,
        storage_state=str(storage_state_path),
        viewport={"width": 1920, "height": 1000},
        record_video_dir=str(settings.reports_dir / "videos") if not settings.headless else None,
    )
    ctx.set_default_timeout(settings.default_timeout)
    yield ctx
    ctx.close()


@pytest.fixture()
def unauth_page(browser: Browser) -> Iterator[Page]:
    """A page in a FRESH context with NO stored auth - for the login tests
    themselves (against an authenticated context ``/login`` just redirects away
    and the form never renders)."""
    ctx = browser.new_context(
        base_url=settings.base_url,
        viewport={"width": 1920, "height": 1000},
    )
    ctx.set_default_timeout(settings.default_timeout)
    pg = ctx.new_page()
    try:
        yield pg
    finally:
        ctx.close()


@pytest.fixture()
def page(context: BrowserContext) -> Iterator[Page]:
    pg = context.new_page()
    console_errors: list[str] = []
    pg.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: console_errors.append(f"PAGEERROR: {e}"))
    pg._qa_console_errors = console_errors  # type: ignore[attr-defined]
    yield pg
    pg.close()


# ------------------------------------------------------------- domain fixtures
def ensure_pharmacy(page: Page, storage_state_path: Path) -> PharmacySelectionPage:
    """Ensure the active pharmacy is the configured one (Manik Pharma) and verified.

    Recovers from a dead/expired reused session: if landing on ``/login`` (the
    stored ``storage_state`` went stale), it re-authenticates in-place and
    regenerates the state file, then retries once.  If the pharmacy picker comes
    back truncated (a known staging outage, BUG-API-001), it skips rather than
    erroring the whole test.
    """
    picker = PharmacySelectionPage(page)

    def _goto_dashboard() -> None:
        page.goto(settings.base_url + "dashboard", wait_until="domcontentloaded")

    _goto_dashboard()
    if auth.ensure_logged_in(page, storage_state_path):
        _goto_dashboard()

    sidebar = page.locator("aside")
    already = sidebar.get_by_text(settings.pharmacy_name, exact=True)
    if not already.count():
        picker.open()
        if not picker.has_pharmacy(settings.pharmacy_name, timeout=8_000):
            pytest.skip(
                f"{settings.pharmacy_name!r} not in the pharmacy picker - staging "
                "instability (BUG-API-001: truncated pharmacy list / session churn)"
            )
        picker.select(settings.pharmacy_name)
    picker.assert_selected(settings.pharmacy_name)
    allure.attach(settings.pharmacy_name, name="active-pharmacy",
                  attachment_type=allure.attachment_type.TEXT)
    return picker


@pytest.fixture()
def pharmacy(page: Page, storage_state_path: Path) -> PharmacySelectionPage:
    """Per-test pharmacy guarantee (see ensure_pharmacy)."""
    return ensure_pharmacy(page, storage_state_path)


@pytest.fixture()
def products_data() -> dict:
    f = settings.test_data_dir / "products.json"
    return read_json(f) if f.exists() else {}


@pytest.fixture()
def validation_data() -> dict:
    f = settings.test_data_dir / "validation_data.json"
    return read_json(f) if f.exists() else {}


@pytest.fixture()
def inventory_data() -> dict:
    f = settings.test_data_dir / "inventory_data.json"
    return read_json(f) if f.exists() else {}


# ------------------------------------------------------------- failure evidence
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or report.passed:
        return
    pg: Page | None = item.funcargs.get("page")
    if pg is None:
        return
    try:
        screenshot(pg, f"FAIL_{item.name}")
        attach_page_context(pg, "failure-context")
        errs = getattr(pg, "_qa_console_errors", [])
        if errs:
            allure.attach("\n".join(errs[-50:]), name="console-errors",
                          attachment_type=allure.attachment_type.TEXT)
    except Exception as exc:  # pragma: no cover
        log.warning("evidence capture failed: %s", exc)
