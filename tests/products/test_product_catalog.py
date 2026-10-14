"""Product Catalog - structure, search, filters, pagination, selection, import.

Verified live 2026-09-08 against Manik Pharma (~41k global products).
"""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from pages.my_products_page import MyProductsPage

pytestmark = [pytest.mark.products]


@allure.epic("Products")
@allure.feature("Product Catalog")
class TestCatalogStructure:

    @allure.story("Catalog loads with the expected layout")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_catalog_loads(self, product_catalog):
        expect(product_catalog.page.locator("main table").nth(1)).to_be_visible()
        assert product_catalog.pagination.total() > 0
        assert product_catalog.row_count() > 0

    @allure.story("Row click opens no detail view (not a feature)")
    @pytest.mark.ui
    def test_row_click_does_nothing(self, product_catalog):
        name = product_catalog.row_names()[0]
        before = product_catalog.page.url
        product_catalog.row(name).locator("td").nth(1).click()
        product_catalog.page.wait_for_timeout(800)
        assert product_catalog.page.url == before
        assert product_catalog.page.locator("[role=dialog], .ant-modal-content").count() == 0


@allure.epic("Products")
@allure.feature("Product Catalog / search & filter")
class TestCatalogSearchFilter:

    @allure.story("Search - no match shows the empty state")
    @pytest.mark.negative
    def test_search_no_match_empty(self, product_catalog):
        product_catalog.search("ZZ_NO_SUCH_CATALOG_ITEM_ZZ_9999")
        assert product_catalog.row_count() == 0
        assert product_catalog.pagination.total() == 0

    @allure.story("Search - partial term filters the list")
    @pytest.mark.regression
    def test_search_partial_filters(self, product_catalog):
        product_catalog.search("paracetamol")
        total = product_catalog.pagination.total()
        assert 0 < total < 41_000
        for name in product_catalog.row_names():
            assert "paracetamol" in name.lower()

    @allure.story("Search - leading/trailing spaces are trimmed")
    @pytest.mark.boundary
    def test_search_trims_spaces(self, product_catalog):
        product_catalog.search("paracetamol")
        n1 = product_catalog.pagination.total()
        product_catalog.search("   paracetamol   ")
        assert product_catalog.pagination.total() == n1

    @allure.story("Company filter narrows the list; Reset Filters restores it")
    @pytest.mark.regression
    def test_company_filter_and_reset(self, product_catalog):
        full = product_catalog.pagination.total()
        product_catalog.filter_by(company="3RD PARTY VENDOR")
        assert 0 < product_catalog.pagination.total() < full
        for company in [product_catalog.row(n).locator("td").nth(2).inner_text().strip()
                        for n in product_catalog.row_names()]:
            assert company == "3RD PARTY VENDOR"
        product_catalog.reset_filters()
        assert product_catalog.pagination.total() == full

    @allure.story("All three filters (Generic + Company + Product Type) combine with AND")
    @pytest.mark.regression
    def test_three_filters_combine(self, product_catalog):
        product_catalog.filter_by(generic="CEFIXIME TRIHYDRATE")
        product_catalog.page.wait_for_url("**genericId=**", timeout=6_000)
        after_generic = product_catalog.pagination.total()
        assert 0 < after_generic < 41_000
        product_catalog.filter_by(company="HALLMARK PHARMACEUTICALS LTD.")
        product_catalog.page.wait_for_url("**companyId=**", timeout=6_000)
        assert product_catalog.pagination.total() <= after_generic
        assert "genericId=" in product_catalog.page.url and "companyId=" in product_catalog.page.url

    @allure.story("BUG-SEARCH-001: a '%' in the search term must not crash the page")
    @allure.issue("BUG-SEARCH-001")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_search_percent_char_does_not_crash(self, product_catalog):
        product_catalog.search("50% off")
        product_catalog.page.wait_for_timeout(1_500)
        main = product_catalog.page.locator("main")
        body_len = len((main.inner_text() or "").strip())
        console = getattr(product_catalog.page, "_qa_console_errors", [])
        uri_err = any("uri malformed" in e.lower() or "urierror" in e.lower() for e in console)
        allure.attach("main length={} uri_error_in_console={}".format(body_len, uri_err),
                      name="after '%' search")
        assert body_len > 0 and not uri_err, (
            "BUG-SEARCH-001 reproduced: '%' in Product Catalog search crashed the page "
            "(main blank={}, URIError={})".format(body_len == 0, uri_err)
        )

    @allure.story("Search with SQL-ish / HTML / unicode input is handled safely")
    @pytest.mark.negative
    @pytest.mark.security
    @pytest.mark.parametrize("term", [
        "' OR 1=1 --",
        "<b>x</b><script>alert(1)</script>",
        "নাপা",          # bangla
        "A" * 200,
    ])
    def test_search_injection_input_is_safe(self, product_catalog, term):
        product_catalog.search(term)
        product_catalog.page.wait_for_timeout(1_200)
        main = product_catalog.page.locator("main")
        assert len((main.inner_text() or "").strip()) > 0, "page went blank for term {!r}".format(term)
        assert main.locator("script, b:has-text('x')").count() == 0, "search input was injected as live HTML"


@allure.epic("Products")
@allure.feature("Product Catalog / pagination")
class TestCatalogPagination:

    @allure.story("Next / page-number / Go-to navigate and sync the URL")
    @pytest.mark.regression
    def test_pagination_and_url_sync(self, product_catalog):
        product_catalog.pagination.next(product_catalog.click)
        assert "page=2" in product_catalog.page.url
        assert product_catalog.pagination.range()[0] == 11
        product_catalog.pagination.go_to_page(100, product_catalog.click)
        product_catalog.page.wait_for_url("**page=100**", timeout=6_000)
        assert product_catalog.pagination.range()[0] == 991

    @allure.story("Items per page changes the page size")
    @pytest.mark.regression
    @pytest.mark.parametrize("size", [20, 50, 100])
    def test_items_per_page(self, product_catalog, size):
        product_catalog.pagination.set_page_size(size, product_catalog.click)
        product_catalog.page.wait_for_url("**size={}**".format(size), timeout=6_000)
        assert product_catalog.pagination.range() == (1, size)

    @allure.story("A URL that already carries filter params restores that state (deep-link)")
    @pytest.mark.regression
    def test_deeplink_restores_filter(self, product_catalog):
        from config import settings
        product_catalog.page.goto(
            settings.base_url + "product-catalog?size=10&page=1&productTypeId=18",
            wait_until="domcontentloaded",
        )
        product_catalog.wait_loaded()
        assert 0 < product_catalog.pagination.total() < 41_000
        chips = product_catalog.page.locator(
            ".ant-select-selection-item, .ant-select-content-has-value"
        ).all_inner_texts()
        assert any("INFUSION" in c.upper() for c in chips), (
            "deep-linked productTypeId=18 did not restore the filter chip: {}".format(chips)
        )


@allure.epic("Products")
@allure.feature("Product Catalog / selection")
class TestCatalogSelection:

    @allure.story("Single row checkbox selects / deselects")
    def test_single_selection_toggles(self, product_catalog):
        name = next(n for n in product_catalog.row_names()
                    if not product_catalog.is_already_imported(n))
        product_catalog.select(name)
        assert product_catalog.is_selected(name)
        assert product_catalog.selected_count() == 1
        product_catalog.deselect(name)
        assert not product_catalog.is_selected(name)

    @allure.story("Multiple selection; Cancel clears everything")
    @pytest.mark.regression
    def test_multi_select_and_cancel(self, product_catalog):
        fresh = [n for n in product_catalog.row_names()
                 if not product_catalog.is_already_imported(n)][:3]
        for n in fresh:
            product_catalog.select(n)
        assert product_catalog.selected_count() == 3
        product_catalog.cancel_selection()
        assert product_catalog.selected_count() == 0

    @allure.story("BUG-CAT-002: 'Select all' selects the WHOLE catalogue with no page-vs-all choice / confirmation")
    @allure.issue("BUG-CAT-002")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_select_all_selects_entire_catalogue(self, product_catalog):
        """One click on the header checkbox selects every product across all
        4,101 pages (button -> 'Import selected (41,005)').  There is no
        'select this page' option and no confirmation before the bulk import."""
        product_catalog.reset_filters()
        total = product_catalog.pagination.total()
        assert total > product_catalog.row_count(), "need a multi-page result to make the point"
        product_catalog.select_all()
        selected = product_catalog.selected_count()
        allure.attach(f"page rows={product_catalog.row_count()}  selected={selected}  total={total}",
                      name="select-all scope")
        # Desired: 'Select all' selects only the visible page.
        assert selected == product_catalog.row_count(), (
            f"BUG-CAT-002 reproduced: 'Select all' selected {selected} (the entire "
            f"catalogue of {total}), not just the {product_catalog.row_count()} visible rows"
        )
        product_catalog.cancel_selection()

    @allure.story("Selection persists across pagination and re-hydrates the checkbox")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    def test_selection_persists_across_pages(self, product_catalog):
        name = next(n for n in product_catalog.row_names()
                    if not product_catalog.is_already_imported(n))
        product_catalog.select(name)
        product_catalog.pagination.next(product_catalog.click)
        assert product_catalog.selected_count() == 1
        product_catalog.pagination.go_to_page(1, product_catalog.click)
        product_catalog.page.wait_for_url("**page=1**", timeout=6_000)
        assert product_catalog.selected_count() == 1
        assert product_catalog.is_selected(name), "checkbox did not re-hydrate on return to page 1"
        product_catalog.cancel_selection()

    @allure.story("Selection count survives a search round-trip")
    @pytest.mark.regression
    def test_selection_persists_across_search(self, product_catalog):
        name = next(n for n in product_catalog.row_names()
                    if not product_catalog.is_already_imported(n))
        product_catalog.select(name)
        product_catalog.search("something-else")
        assert product_catalog.selected_count() == 1
        product_catalog.search_field.clear()
        assert product_catalog.selected_count() == 1
        product_catalog.cancel_selection()


@allure.epic("Products")
@allure.feature("Product Catalog / import to My Products")
class TestCatalogImport:

    @allure.story("Import one row; it appears in My Products; row becomes 'Imported'")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.integration
    def test_import_single_row(self, product_catalog, page, qa_records):
        name = next(n for n in product_catalog.row_names()
                    if not product_catalog.is_already_imported(n))
        toast = product_catalog.import_row(name)
        assert "import" in toast.lower()
        qa_records.append(name)
        expect(product_catalog.row(name).get_by_text("Imported")).to_be_visible(timeout=6_000)

        my_products = MyProductsPage(page).open().wait_loaded()
        my_products.search(name.split()[0])
        assert my_products.has_product(name.split()[0])

    @allure.story("BUG-CAT-003: the row Import button is disabled while its request is in flight")
    @allure.issue("BUG-CAT-003")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_row_import_button_is_guarded_against_rapid_clicks(self, product_catalog, qa_records):
        name = next(n for n in product_catalog.row_names()
                    if not product_catalog.is_already_imported(n))
        btn = product_catalog.row(name).get_by_role("button", name="Import")
        calls: list = []
        product_catalog.page.on(
            "request",
            lambda r: calls.append(r.url) if "/pharmacy-products/import/" in r.url else None,
        )
        for _ in range(3):                      # rapid triple-click, no wait
            try:
                btn.click(timeout=800, no_wait_after=True)
            except Exception:
                break
        product_catalog.page.wait_for_timeout(2_000)
        qa_records.append(name)
        allure.attach("import POSTs fired: {}".format(len(calls)), name="rapid-click")
        assert len(calls) <= 1, (
            "BUG-CAT-003 reproduced: {} import requests fired for one product on a "
            "triple-click (button not disabled during the request)".format(len(calls))
        )

    @allure.story("BUG-CAT-001 (partial): already-imported rows stay selectable; excludedProducts misreported")
    @allure.issue("BUG-CAT-001")
    @pytest.mark.negative
    @pytest.mark.integration
    def test_bulk_import_should_exclude_already_imported(self, product_catalog):
        """2026-09-09 recheck: the importedProducts OVER-COUNT is fixed (bulk of
        [fresh + already-imported] now returns importedProducts:1).  Still open:
        the already-imported row's checkbox is not disabled, Select All includes
        it, and the response reports excludedProducts:0 instead of 1."""
        imported = next((n for n in product_catalog.row_names()
                         if product_catalog.is_already_imported(n)), None)
        if imported is None:
            pytest.skip("no already-imported catalog row on this page to test with")
        # the per-row button is correctly disabled...
        assert product_catalog.row(imported).get_by_role("button", name="Import").count() == 0
        # ...but the checkbox is still enabled and selectable (the residual bug).
        assert product_catalog.row_checkbox(imported).is_disabled(), (
            "BUG-CAT-001 (residual): an already-imported product's checkbox is still "
            "enabled; it is included in Select All and sent in the bulk payload, and "
            "the response still reports excludedProducts:0"
        )
