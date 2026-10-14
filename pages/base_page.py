"""BasePage - shared page behaviour for every Page Object.

Locators + page-specific actions live in subclasses.  This class only provides
generic, reusable plumbing: navigation, waiting, evidence, and a **resilient
click** that copes with the app's React/AntD event handling.

Why the resilient click?
------------------------
During exploratory testing the app (an AntD + React 18 build) intermittently
ignored Playwright's synthetic ``click()`` while still responding to a full
pointer-event sequence.  ``click()`` here tries the native click first and, only
if the expected effect is not observed, falls back to a JS-dispatched
``pointerdown -> mousedown -> pointerup -> mouseup -> click`` sequence.  Callers
can pass ``expect=`` (a zero-arg predicate) so the helper knows whether the
native attempt actually worked.
"""
from __future__ import annotations

import time
from typing import Callable

import allure
from playwright.sync_api import Locator, Page, expect

from config import settings
from utils.helpers import screenshot
from utils.logger import get_logger

_JS_REAL_CLICK = """
(el) => {
  el.scrollIntoView({ block: 'center', inline: 'center' });
  const r = el.getBoundingClientRect();
  const base = { bubbles: true, cancelable: true, composed: true, view: window,
                 button: 0, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
  const seq = ['pointerover','pointerenter','pointermove','pointerdown','mousedown',
               'pointerup','mouseup','click'];
  for (const type of seq) {
    const C = type.startsWith('pointer') ? PointerEvent : MouseEvent;
    el.dispatchEvent(new C(type, { ...base, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
  }
}
"""


class BasePage:
    #: subclasses set this to the route slug (see utils.constants.ROUTES)
    route: str = ""

    def __init__(self, page: Page):
        self.page = page
        self.log = get_logger(self.__class__.__name__)
        self.page.set_default_timeout(settings.default_timeout)
        self.page.set_default_navigation_timeout(settings.nav_timeout)

    # ------------------------------------------------------------------ nav
    @property
    def base_url(self) -> str:
        return settings.base_url

    def open(self, route: str | None = None) -> "BasePage":
        slug = route if route is not None else self.route
        url = self.base_url + slug.lstrip("/")
        with allure.step(f"Open {url}"):
            self.page.goto(url, wait_until="domcontentloaded")
            self.wait_for_app_ready()
        return self

    def wait_for_app_ready(self) -> None:
        """Wait until the SPA shell has painted (sidebar present) and network calmed."""
        try:
            self.page.wait_for_selector("aside, .ant-menu, [class*='sidebar']", timeout=settings.default_timeout)
        except Exception:
            self.log.warning("app shell selector not found within timeout on %s", self.page.url)
        try:
            self.page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            pass

    def reload(self) -> None:
        self.page.reload(wait_until="domcontentloaded")
        self.wait_for_app_ready()

    # --------------------------------------------------------------- clicks
    def click(
        self,
        target: Locator | str,
        *,
        expect_effect: Callable[[], bool] | None = None,
        description: str = "",
    ) -> None:
        """Click ``target`` robustly, then wait for the UI to go quiet.

        Playwright's own ``click()`` auto-waits for actionability.  The only
        extra waiting here is:
          * ``expect_effect`` - an optional zero-arg predicate polled until True;
            it both confirms the native click worked and drives the JS fallback
            (this app occasionally ignores synthetic clicks);
          * ``_settle()`` - a *condition-based* wait for AntD wave/spin animations
            and in-flight requests to finish (never a fixed sleep).
        """
        loc = self.page.locator(target) if isinstance(target, str) else target
        label = description or (target if isinstance(target, str) else "locator")
        with allure.step(f"Click: {label}"):
            loc.first.wait_for(state="visible")
            try:
                loc.first.click(timeout=5_000)
            except Exception as exc:  # noqa: BLE001 - fall through to JS path
                self.log.info("native click failed for %s (%s); using JS fallback", label, exc)
                self._js_click(loc)
                self._settle()
                return

            if expect_effect is None:
                self._settle()
                return

            # Give the effect a generous window - a slow/degraded backend can take
            # several seconds to navigate or open a drawer after a *successful*
            # click.  (Too short a window here made a slow-but-fine click look
            # like a no-op and triggered a destructive JS re-click.)
            if self._poll(expect_effect, timeout=8_000):
                self._settle()
                return

            # If the target has since detached, the native click almost certainly
            # worked (it navigated / replaced the DOM) - do NOT re-click.
            if not self._is_attached(loc):
                self.log.info("native click detached %s; treating as effective", label)
                self._settle()
                return

            self.log.info("native click had no effect for %s; using JS fallback", label)
            self._js_click(loc)
            if not self._poll(expect_effect, timeout=5_000) and self._is_attached(loc):
                self.log.warning("JS fallback click produced no observed effect for %s", label)
            self._settle()

    @staticmethod
    def _is_attached(loc: Locator) -> bool:
        try:
            return loc.first.count() > 0
        except Exception:
            return False

    def _js_click(self, loc: Locator) -> None:
        """Dispatch a full pointer-event sequence via JS.  Bounded and safe: if
        the element is gone (navigation) this is a no-op, never a 30s hang."""
        try:
            loc.first.wait_for(state="attached", timeout=1_000)
        except Exception:
            self.log.info("JS fallback skipped: target no longer attached")
            return
        try:
            loc.first.evaluate(_JS_REAL_CLICK, timeout=5_000)
        except Exception as exc:  # noqa: BLE001
            self.log.info("JS fallback click could not run (%s)", exc)

    @staticmethod
    def _poll(predicate: Callable[[], bool], timeout: int = 2_000, interval: int = 50) -> bool:
        """Poll a Python predicate until it returns truthy or the timeout elapses.

        Used only for predicates Playwright's own waiters can't express
        (e.g. ``lambda: some_locator.count() == 0``).  ``interval`` is the poll
        cadence of this condition wait - not a fixed delay.
        """
        deadline = time.monotonic() + timeout / 1_000
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            time.sleep(interval / 1_000)
        try:
            return bool(predicate())
        except Exception:
            return False

    def _settle(self, cap_ms: int = 1_500) -> None:
        """Wait for the page to stop moving: no AntD ripple / spinner running and
        the network briefly idle.  Bounded by ``cap_ms``; no fixed sleep."""
        try:
            self.page.wait_for_function(
                """() => {
                    if (document.querySelector('.ant-wave, .ant-click-animating-node')) return false;
                    if (document.querySelector('.ant-spin-spinning')) return false;
                    return true;
                }""",
                timeout=cap_ms,
            )
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=cap_ms)
        except Exception:
            pass

    # ---------------------------------------------------------------- typing
    def fill(self, target: Locator | str, value: str, *, description: str = "") -> None:
        loc = self.page.locator(target) if isinstance(target, str) else target
        with allure.step(f"Fill {description or 'field'} = {value!r}"):
            loc.first.wait_for(state="visible")
            loc.first.fill("")
            loc.first.fill(str(value))

    def type_slow(self, target: Locator | str, value: str, delay: int = 40) -> None:
        loc = self.page.locator(target) if isinstance(target, str) else target
        loc.first.click()
        loc.first.press_sequentially(str(value), delay=delay)

    # ---------------------------------------------------------------- reads
    def toast_messages(self) -> list[str]:
        sel = ".ant-message-notice, .ant-notification-notice, [role='alert']"
        return [t.strip() for t in self.page.locator(sel).all_inner_texts() if t.strip()]

    def wait_for_toast(self, contains: str = "", timeout: int = 8_000) -> str:
        loc = self.page.locator(".ant-message-notice, .ant-notification-notice, [role='alert']")
        loc.first.wait_for(state="visible", timeout=timeout)
        text = loc.first.inner_text().strip()
        if contains:
            expect(loc.filter(has_text=contains).first).to_be_visible(timeout=timeout)
        return text

    def form_errors(self, scope: Locator | None = None) -> list[str]:
        root = scope or self.page
        sel = ".ant-form-item-explain-error, .ant-form-item-explain"
        return [t.strip() for t in root.locator(sel).all_inner_texts() if t.strip()]

    def current_pharmacy(self) -> str:
        loc = self.page.locator("aside").get_by_text("Change Pharmacy").locator("xpath=preceding-sibling::*[1]")
        try:
            return loc.first.inner_text().strip()
        except Exception:
            return self.page.locator("aside p").first.inner_text().strip()

    # ------------------------------------------------------------- evidence
    def capture(self, name: str) -> None:
        screenshot(self.page, name)
