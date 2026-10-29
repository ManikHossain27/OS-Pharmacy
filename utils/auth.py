"""Single place that logs in. Credentials come from `.env` via `config.settings`
(LOGIN_PHONE / LOGIN_PASSWORD) and are only ever typed by `LoginPage.login`.

Everything that needs an authenticated browser (pytest fixtures, tools/ scripts,
ad-hoc exploration) goes through here instead of re-implementing login.

CLI - refresh the saved session (e.g. after it expired):
    python -m utils.auth                 # headless, writes settings.auth_state_path
    python -m utils.auth --headed        # watch it log in
    python -m utils.auth --out other.json
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from config import settings
from pages.login_page import LoginPage

log = logging.getLogger("auth")

VIEWPORT = {"width": 1920, "height": 1000}


def login(page: Page, state_path: Path | None = None) -> None:
    """Log in on `page` and, if `state_path` is given, persist the session there."""
    LoginPage(page).login()
    page.wait_for_url(lambda u: "/login" not in u, timeout=settings.nav_timeout)
    if state_path:
        save_state(page.context, state_path)


def save_state(ctx: BrowserContext, path: Path | None = None) -> Path:
    path = Path(path or settings.auth_state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ctx.storage_state(path=str(path))
    return path


def refresh_state(browser: Browser, path: Path | None = None) -> Path:
    """Always log in from scratch in a throw-away context and save the session."""
    path = Path(path or settings.auth_state_path)
    ctx = browser.new_context(base_url=settings.base_url, viewport=VIEWPORT)
    try:
        login(ctx.new_page(), path)
    finally:
        ctx.close()
    log.info("Saved fresh auth state: %s", path)
    return path


def ensure_state(browser: Browser, path: Path | None = None) -> Path:
    """Return a saved session, logging in only when none exists (or reuse is off)."""
    path = Path(path or settings.auth_state_path)
    if settings.reuse_auth_state and path.exists() and path.stat().st_size > 0:
        log.info("Reusing existing auth state: %s", path)
        return path
    return refresh_state(browser, path)


def ensure_logged_in(page: Page, state_path: Path | None = None) -> bool:
    """If `page` was bounced to /login (dead session), log in again in place.
    Returns True when a re-login happened."""
    if "/login" not in page.url:
        return False
    log.warning("session is dead - logging in again")
    login(page, state_path or settings.auth_state_path)
    return True


def authenticated_context(browser: Browser, path: Path | None = None, **kwargs) -> BrowserContext:
    """New context pre-loaded with the saved session (created if missing)."""
    kwargs.setdefault("viewport", VIEWPORT)
    return browser.new_context(base_url=settings.base_url,
                               storage_state=str(ensure_state(browser, path)), **kwargs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--out", type=Path, default=None, help="state file (default: settings.auth_state_path)")
    args = ap.parse_args()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=not args.headed)
        try:
            print("saved", refresh_state(b, args.out))
        finally:
            b.close()


if __name__ == "__main__":
    main()
