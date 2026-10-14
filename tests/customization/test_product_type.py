"""Customizations -> Product Type List.

Focus: numeric ordering field (Sort Order / Sequence / Priority) validation and
that raw backend type errors (e.g. "expected a value of type int") never reach
the user.
"""
from __future__ import annotations

import allure
import pytest

from pages.my_products_page import MyProductsPage
from utils import data_generator as dg

pytestmark = [pytest.mark.customization]

RAW_ERROR_FRAGMENTS = (
    "expected a value of type",
    "traceback",
    "int()",
    "valueerror",
    "typeerror",
    "cannot convert",
    "nonetype",
    "500 internal",
)


@allure.epic("Customization")
@allure.feature("Product Type List")
class TestProductTypeList:

    @allure.story("List loads")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_list_loads(self, product_type_list):
        assert product_type_list.page.locator("table").first.is_visible()

    @allure.story("The Add form has no Sort Order / Sequence / Priority field")
    @allure.severity(allure.severity_level.MINOR)
    @pytest.mark.ui
    def test_no_sort_order_field(self, product_type_list):
        # As of 2026-09-08 the form is Name-only. If a future build adds an
        # ordering field, update the boundary matrix below (currently N/A).
        assert product_type_list.has_sort_order_field() is False

    @allure.story("BUG-PTYPE-001: create fails with a raw backend error (missing sortOrder/slug)")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.issue("BUG-PTYPE-001")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_create_product_type_leaks_raw_backend_error(self, product_type_list):
        name = dg.product_type_name()
        result = product_type_list.create_with_sort_order(name, 900)
        text = str(result).lower()
        allure.attach(str(result), name="create result")
        for frag in RAW_ERROR_FRAGMENTS:
            assert frag not in text, (
                f"BUG-PTYPE-001 reproduced: raw backend error leaked -> {result!r}"
            )
        assert "slug must not be blank" not in text, (
            f"BUG-PTYPE-001 reproduced: 'slug must not be blank' shown -> {result!r}"
        )

    @allure.story("Empty name rejected")
    @pytest.mark.negative
    def test_empty_name_rejected(self, product_type_list):
        assert product_type_list.create_expecting_error(""), "empty product type accepted"

    @allure.story("BUG-PTYPE-002: editing a Product Type also leaks the raw 'sortOrder ... type int' error")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.issue("BUG-PTYPE-002")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_edit_product_type_leaks_raw_backend_error(self, product_type_list):
        """The Edit path has the same root cause as create (BUG-PTYPE-001): the
        PUT body carries only {name}, so the backend answers 400 with
        "Invalid value for field 'sortOrder': expected a value of type int.".
        """
        target = product_type_list.first_editable_type()
        if not target:
            pytest.skip(
                "No pharmacy-scoped (editable) product type on the visible page - "
                "seed one first, e.g. 'QA SEED TYPE <date> 01'."
            )
        result = product_type_list.edit_expecting_error(target, f"{target} EDITED")
        text = str(result).lower()
        allure.attach(str(result), name="edit result")
        for frag in RAW_ERROR_FRAGMENTS:
            assert frag not in text, (
                f"BUG-PTYPE-002 reproduced: raw backend error leaked on edit -> {result!r}"
            )
        # And the rename must actually have taken effect.
        product_type_list.reload()
        product_type_list.search(f"{target} EDITED")
        assert product_type_list.has_entity(f"{target} EDITED"), (
            f"BUG-PTYPE-002: edit of {target!r} did not persist -> {result!r}"
        )

    @allure.story("Duplicate name prevented")
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.blocked
    def test_duplicate_prevented(self):
        pytest.skip("Cannot create a Product Type via the UI at all - BUG-PTYPE-001")

    # ---------------- Sort Order numeric field --------------------------------
    # N/A: the Add form has no Sort Order / Sequence / Priority field
    # (see test_no_sort_order_field). The backend's hidden sortOrder requirement
    # is covered by test_create_product_type_leaks_raw_backend_error.
    @allure.story("Sort Order boundary matrix - N/A, no such field in this build")
    @pytest.mark.skip(reason="Product Type Add form has no ordering field (2026-09-08). See BUG-PTYPE-001.")
    @pytest.mark.parametrize("value", ["", "abc", "-1", "1.5", "!!", 0, 1, "99999999999999999999"])
    def test_sort_order_values(self, value):
        ...


@allure.epic("Customization")
@allure.feature("Product Type <-> Add Product integration")
class TestProductTypeIntegration:

    @allure.story("Existing product type is selectable in Add Product")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.integration
    def test_existing_type_selectable_in_add_product(self, product_type_list, page):
        # UI-created types are blocked (BUG-PTYPE-001); verify the integration
        # with a type that already exists (e.g. the QA seed 'QA SEED TYPE 260908 01'
        # or any listed type).
        product_type_list.wait_loaded()
        first_type = product_type_list.table.cell(0, "Product Type")
        my_products = MyProductsPage(page).open().wait_loaded()
        drawer = my_products.open_add_product()
        drawer.product_type.open()
        opts = drawer.product_type.options(filter_text=first_type[:6])
        assert any(first_type in o for o in opts), (
            f"product type {first_type!r} from the list is not offered in Add Product"
        )

    @allure.story("QA-seeded type created in Customization is selectable in Add Product")
    @pytest.mark.integration
    def test_qa_seed_type_selectable(self, page):
        my_products = MyProductsPage(page).open().wait_loaded()
        drawer = my_products.open_add_product()
        drawer.product_type.open()
        opts = drawer.product_type.options(filter_text="QA SEED TYPE 260908")
        if not opts:
            pytest.skip("QA SEED TYPE 260908 01 not present - seed it first")
        assert any("QA SEED TYPE 260908 01" == o for o in opts)
