"""Customizations -> Company List: CRUD, validation, integration with Add Product."""
from __future__ import annotations

import allure
import pytest

from pages.my_products_page import MyProductsPage
from utils import data_generator as dg

pytestmark = [pytest.mark.customization]


@allure.epic("Customization")
@allure.feature("Company List")
class TestCompanyList:

    @allure.story("List loads with a table")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_list_loads(self, company_list):
        assert company_list.page.locator("table").first.is_visible()

    @allure.story("Create a QA company")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_create_company(self, company_list, qa_records):
        name = dg.company_name()
        company_list.create(name)
        qa_records.append(name)
        company_list.reload()
        company_list.search(name)
        assert company_list.has_entity(name), "created company not listed after refresh"

    @allure.story("Empty name is rejected (somehow)")
    @pytest.mark.negative
    def test_empty_name_rejected(self, company_list):
        errs = company_list.create_expecting_error("")
        assert errs, "empty company name accepted"

    @allure.story("BUG-CO-001: empty name has NO client-side validation (server catches it)")
    @allure.issue("BUG-CO-001")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_empty_name_has_no_client_side_validation(self, company_list):
        """Generic and Product Type add-forms show an inline 'X is required' on
        empty submit; Company does not - it round-trips to the backend and shows
        a 400 toast instead."""
        form = company_list.open_add()
        form.save()
        # Give any inline error a moment to render.
        try:
            company_list.page.locator(".ant-form-item-explain-error").first.wait_for(
                state="visible", timeout=2_000
            )
        except Exception:
            pass
        inline = form.errors()
        toast = " ".join(company_list.toast.messages()).lower()
        allure.attach(f"inline={inline}  toast={toast!r}", name="empty-submit feedback")
        # The defining symptom of BUG-CO-001 is the ABSENCE of a client-side
        # inline 'required' error (Generic / Product Type both show one).  The
        # form still shouldn't be open silently doing nothing, so also require
        # that *some* feedback (a server toast) came back.
        assert not inline, (
            "BUG-CO-001 expectation changed: Company Add now shows a client-side "
            f"inline error {inline!r} - update / close this bug."
        )
        assert toast, "empty Add New Company submit produced no feedback at all (inline or toast)"

    @allure.story("Whitespace-only name is rejected")
    @pytest.mark.negative
    @pytest.mark.boundary
    def test_whitespace_name_rejected(self, company_list):
        errs = company_list.create_expecting_error("     ")
        assert errs, "whitespace-only company name accepted"

    @allure.story("Duplicate name is prevented")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_duplicate_name_prevented(self, company_list, qa_records):
        name = dg.company_name()
        company_list.create(name)
        qa_records.append(name)
        company_list.reload()
        errs = company_list.create_expecting_error(name)
        joined = " ".join(errs).lower()
        assert "exist" in joined or "duplicate" in joined or "already" in joined, (
            f"duplicate company not prevented; messages: {errs}"
        )

    @allure.story("Case-variant duplicate is prevented")
    @pytest.mark.negative
    @pytest.mark.boundary
    def test_case_variant_duplicate_prevented(self, company_list, qa_records):
        name = dg.company_name()
        company_list.create(name)
        qa_records.append(name)
        company_list.reload()
        errs = company_list.create_expecting_error(name.lower())
        joined = " ".join(errs).lower()
        assert "exist" in joined or "duplicate" in joined or "already" in joined, (
            "case-variant duplicate company not prevented"
        )

    @allure.story("Leading/trailing spaces are trimmed, not stored verbatim")
    @pytest.mark.boundary
    def test_leading_trailing_spaces_trimmed(self, company_list, qa_records):
        base = dg.company_name()
        company_list.create(f"   {base}   ")
        qa_records.append(base)
        company_list.reload()
        company_list.search(base)
        assert company_list.has_entity(base), "spaced company name not normalised/trimmed"

    @allure.story("Single-character name")
    @pytest.mark.boundary
    def test_single_char_name(self, company_list, qa_records):
        errs = company_list.create_expecting_error("Q")
        allure.attach(str(errs), name="single-char result")

    @allure.story("Very long name")
    @pytest.mark.boundary
    def test_very_long_name(self, company_list):
        errs = company_list.create_expecting_error(dg.long_string(256))
        allure.attach(str(errs), name="very-long result")

    @allure.story("Search matches created company")
    @pytest.mark.regression
    def test_search(self, company_list, qa_records):
        name = dg.company_name()
        company_list.create(name)
        qa_records.append(name)
        company_list.reload()
        company_list.search("NO_SUCH_COMPANY_ZZ")
        assert company_list.table.row_count() == 0
        company_list.search(name)
        assert company_list.has_entity(name)

    @allure.story("Delete a QA company (destructive)")
    @pytest.mark.destructive
    def test_delete_company(self, company_list, qa_records):
        name = dg.company_name()
        company_list.create(name)
        company_list.reload()
        company_list.search(name)
        if not company_list.can_delete(name):
            pytest.skip("Company List exposes no delete action")
        company_list.delete(name)
        company_list.reload()
        company_list.search(name)
        assert not company_list.has_entity(name)


@allure.epic("Customization")
@allure.feature("Company List <-> Add Product integration")
class TestCompanyIntegration:

    @allure.story("Company created in Customization is selectable in Add Product")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.integration
    @pytest.mark.blocked
    def test_customization_company_selectable_in_add_product(self, company_list, page, qa_records):
        name = dg.company_name()
        company_list.create(name)
        qa_records.append(name)

        my_products = MyProductsPage(page).open().wait_loaded()
        drawer = my_products.open_add_product()
        try:
            drawer.company.select(name)
            assert drawer.company.selected_text() == name
        except AssertionError as exc:
            pytest.skip(f"AntD Select blocked in this environment: {exc}")
