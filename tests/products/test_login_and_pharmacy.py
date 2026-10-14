"""Login & Pharmacy selection - smoke / prod-safe."""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from config import settings
from pages.login_page import LoginPage
from pages.pharmacy_selection_page import PharmacySelectionPage

pytestmark = [pytest.mark.products, pytest.mark.smoke]


@allure.epic("Access")
@allure.feature("Authentication")
class TestLogin:
    """These run on a FRESH unauthenticated context - against the shared
    authenticated `page` fixture, `/login` just redirects and there is no form."""

    @allure.story("Successful login")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_valid_login_lands_authenticated(self, unauth_page):
        LoginPage(unauth_page).login()
        assert "/login" not in unauth_page.url, "still on /login after valid credentials"

    @allure.story("Invalid login is rejected")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_invalid_password_is_rejected(self, unauth_page):
        msg = LoginPage(unauth_page).login_expecting_error(settings.login_phone, "wrong-password-xyz")
        assert "/login" in unauth_page.url, "unexpectedly authenticated with a wrong password"
        assert msg, "no visible error message for invalid credentials"

    @allure.story("Empty credentials show field validation")
    @pytest.mark.negative
    def test_empty_credentials_show_validation(self, unauth_page):
        lp = LoginPage(unauth_page)
        lp.open()
        lp.click(lp.sign_in_btn, description="Sign In (empty form)")
        expect(unauth_page.locator(".ant-form-item-explain-error").first).to_be_visible(timeout=6_000)
        errors = lp.field_validation_errors()
        assert errors, "empty login submitted without any field validation"


@allure.epic("Access")
@allure.feature("Pharmacy selection")
class TestPharmacySelection:

    @allure.story("Select and verify Manik Pharma")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_select_manik_pharma_and_verify(self, unauth_page):
        LoginPage(unauth_page).login()
        picker = PharmacySelectionPage(unauth_page)
        picker.open()
        if not picker.has_pharmacy(settings.pharmacy_name):
            pytest.skip(
                f"{settings.pharmacy_name!r} not in the pharmacy picker - "
                "environment issue (see BUG-API-001: truncated pharmacy list)"
            )
        picker.select(settings.pharmacy_name)
        picker.assert_selected(settings.pharmacy_name)

    @allure.story("Active pharmacy persists after reload")
    def test_pharmacy_persists_after_reload(self, pharmacy, page):
        page.reload(wait_until="domcontentloaded")
        pharmacy.assert_selected(settings.pharmacy_name)
