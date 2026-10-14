"""Add Company / Add Generic from inside the Add New Product drawer.

Confirmed live 2026-09-08: the green [+] buttons beside Company and Generic in
the drawer are **non-functional** (BUG-PROD-002).  These tests assert that until
the feature is fixed; the two-way sync scenarios stay ``blocked`` because their
entry point is broken.
"""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import TimeoutError as PWTimeout, expect

pytestmark = [pytest.mark.products, pytest.mark.integration]


def _assert_opens_a_new_dialog(add_product, click_target, description: str) -> None:
    """Click and expect a NEW dialog/modal to appear.  Currently (BUG-PROD-002)
    nothing opens, so this fails with a clear message once the button works."""
    dialogs = add_product.page.locator("[role=dialog], .ant-modal-content")
    before = dialogs.count()
    add_product.click(click_target, description=description)
    try:
        expect(dialogs).to_have_count(before + 1, timeout=4_000)
    except (AssertionError, PWTimeout):
        pytest.fail(f"BUG-PROD-002 reproduced: {description} opened no dialog")


@allure.epic("Products")
@allure.feature("Add Company from Add New Product")
class TestAddCompanyFromDrawer:

    @allure.story("BUG-PROD-002: the [+] Add-Company button does nothing")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.negative
    def test_plus_add_company_is_dead(self, add_product):
        plus = add_product.company_plus_button()
        assert plus.count() == 1, "the [+] button next to Company should exist"
        _assert_opens_a_new_dialog(add_product, plus, "+ add company")

    @allure.story("Company created from drawer syncs to dropdown + Customization list")
    @pytest.mark.blocked
    def test_company_created_from_drawer_syncs_everywhere(self):
        pytest.skip("Entry point broken - BUG-PROD-002 (the drawer [+] button does nothing)")

    @allure.story("Duplicate company from drawer is prevented")
    @pytest.mark.negative
    @pytest.mark.blocked
    def test_duplicate_company_prevented(self):
        pytest.skip("Entry point broken - BUG-PROD-002")


@allure.epic("Products")
@allure.feature("Add Generic from Add New Product")
class TestAddGenericFromDrawer:

    @allure.story("BUG-PROD-002: the [+] Add-Generic button does nothing")
    @pytest.mark.negative
    def test_plus_add_generic_is_dead(self, add_product):
        plus = add_product.generic_plus_button()
        assert plus.count() == 1
        _assert_opens_a_new_dialog(add_product, plus, "+ add generic")

    @allure.story("Generic created from drawer syncs to Generic List")
    @pytest.mark.blocked
    def test_generic_created_from_drawer_syncs(self):
        pytest.skip("Entry point broken - BUG-PROD-002")
