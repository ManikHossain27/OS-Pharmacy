"""Login page.

The visible label is "Phone number" (placeholder 01XXX-XXXXXX) but the field
currently also accepts an email address.
"""
from __future__ import annotations

import allure
from playwright.sync_api import expect

from config import settings
from pages.base_page import BasePage
from utils.constants import ROUTES
from utils.helpers import mask_secret


class LoginPage(BasePage):
    route = ROUTES["login"]

    def __init__(self, page):
        super().__init__(page)
        self.phone_input = page.get_by_role("textbox", name="Phone number")
        self.password_input = page.get_by_role("textbox", name="Password")
        self.show_password_btn = page.get_by_role("button", name="Show")
        self.sign_in_btn = page.get_by_role("button", name="Sign In")
        self.create_account_link = page.get_by_role("link", name="Create a New Account")

    # ------------------------------------------------------------------
    def open(self, route: str | None = None) -> "LoginPage":
        """Go to /login and wait for the FORM (not the app shell - the login
        page has no sidebar, so BasePage.wait_for_app_ready would just burn the
        timeout every call)."""
        self.page.goto(self.base_url + (route or self.route).lstrip("/"),
                       wait_until="domcontentloaded")
        expect(self.phone_input).to_be_visible(timeout=settings.nav_timeout)
        return self

    @allure.step("Log in as {phone}")
    def login(self, phone: str | None = None, password: str | None = None) -> None:
        phone = phone or settings.login_phone
        password = password or settings.login_password
        assert phone and password, "LOGIN_PHONE / LOGIN_PASSWORD not configured"

        self.open()  # /login + wait for the form (no app-shell wait)
        self.fill(self.phone_input, phone, description="Phone number")
        self.fill(self.password_input, password, description="Password")
        self.log.info("submitting login for %s", mask_secret(phone, keep=4))

        # Plain click - the wait_for_url below is the real synchronisation.  A
        # slow auth round-trip must NOT be misread as "click had no effect".
        self.click(self.sign_in_btn, description="Sign In")
        try:
            self.page.wait_for_url(lambda u: "/login" not in u, timeout=settings.nav_timeout)
        except Exception:
            # Surface why login didn't proceed (bad creds, backend 5xx, ...).
            errs = self.form_errors() + self.toast_messages()
            raise AssertionError(
                f"Login did not leave /login within {settings.nav_timeout}ms. "
                f"Page feedback: {errs or 'none'}; url={self.page.url}"
            )

    def login_expecting_error(self, phone: str, password: str) -> str:
        self.open()
        self.fill(self.phone_input, phone, description="Phone number")
        self.fill(self.password_input, password, description="Password")
        self.click(self.sign_in_btn, description="Sign In")
        # Wait for the outcome to actually render: an inline error, a toast, or a
        # navigation away from /login - whichever happens first.
        outcome = self.page.locator(
            ".ant-form-item-explain-error, .ant-message-notice, .ant-notification-notice, [role='alert']"
        )
        try:
            outcome.first.wait_for(state="visible", timeout=8_000)
        except Exception:
            if "/login" not in self.page.url:  # unexpectedly succeeded
                return ""
        errs = self.form_errors() + self.toast_messages()
        return " | ".join(errs)

    def field_validation_errors(self) -> list[str]:
        return self.form_errors()
