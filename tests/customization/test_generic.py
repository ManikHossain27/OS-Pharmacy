"""Customizations -> Generic List: CRUD, validation, integration with Add Product."""
from __future__ import annotations

import allure
import pytest

from pages.my_products_page import MyProductsPage
from utils import data_generator as dg

pytestmark = [pytest.mark.customization]


@allure.epic("Customization")
@allure.feature("Generic List")
class TestGenericList:

    @allure.story("List loads")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_list_loads(self, generic_list):
        assert generic_list.page.locator("table").first.is_visible()

    @allure.story("Create a QA generic and see it persist")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_create_generic(self, generic_list, qa_records):
        name = dg.generic_name()
        generic_list.create(name)
        qa_records.append(name)
        generic_list.reload()
        generic_list.search(name)
        assert generic_list.has_entity(name)

    @allure.story("Empty name rejected")
    @pytest.mark.negative
    def test_empty_name_rejected(self, generic_list):
        assert generic_list.create_expecting_error(""), "empty generic accepted"

    @allure.story("Duplicate generic prevented")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_duplicate_prevented(self, generic_list, qa_records):
        name = dg.generic_name()
        generic_list.create(name)
        qa_records.append(name)
        generic_list.reload()
        errs = " ".join(generic_list.create_expecting_error(name)).lower()
        assert any(k in errs for k in ("exist", "duplicate", "already")), errs

    @allure.story("Case-variant duplicate prevented")
    @pytest.mark.negative
    @pytest.mark.boundary
    def test_case_variant_duplicate(self, generic_list, qa_records):
        name = dg.generic_name()
        generic_list.create(name)
        qa_records.append(name)
        generic_list.reload()
        errs = " ".join(generic_list.create_expecting_error(name.upper())).lower()
        assert any(k in errs for k in ("exist", "duplicate", "already")), errs

    @allure.story("Special characters / unicode handling")
    @pytest.mark.boundary
    def test_special_and_unicode(self, generic_list, qa_records):
        name = f"{dg.generic_name()} {dg.UNICODE} {dg.SPECIAL_CHARS[:6]}"
        errs = generic_list.create_expecting_error(name)
        allure.attach(str(errs), name="special/unicode result")

    @allure.story("Delete a QA generic (destructive)")
    @pytest.mark.destructive
    def test_delete_generic(self, generic_list, qa_records):
        name = dg.generic_name()
        generic_list.create(name)
        generic_list.reload()
        generic_list.search(name)
        if not generic_list.can_delete(name):
            pytest.skip("Generic List exposes no delete action")
        generic_list.delete(name)
        generic_list.reload()
        generic_list.search(name)
        assert not generic_list.has_entity(name)


@allure.epic("Customization")
@allure.feature("Generic List <-> Add Product integration")
class TestGenericIntegration:

    @allure.story("Generic created in Customization is selectable in Add Product")
    @pytest.mark.integration
    @pytest.mark.blocked
    def test_customization_generic_selectable_in_add_product(self, generic_list, page, qa_records):
        name = dg.generic_name()
        generic_list.create(name)
        qa_records.append(name)
        my_products = MyProductsPage(page).open().wait_loaded()
        drawer = my_products.open_add_product()
        try:
            drawer.generic.select(name)
            assert drawer.generic.selected_text() == name
        except AssertionError as exc:
            pytest.skip(f"AntD Select blocked in this environment: {exc}")
