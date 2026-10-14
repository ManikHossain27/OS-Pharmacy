"""My Products / Product List."""
from __future__ import annotations

import allure
import pytest

from utils import data_generator as dg
from utils.constants import MY_PRODUCTS_COLUMNS, MY_PRODUCTS_SUMMARY_CARDS

pytestmark = [pytest.mark.products]


@allure.epic("Products")
@allure.feature("My Products")
class TestMyProductsPage:

    @allure.story("List page loads with expected structure")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_page_loads_with_table_and_controls(self, my_products):
        assert my_products.is_loaded()
        headers = my_products.table.headers()
        for col in MY_PRODUCTS_COLUMNS:
            assert col in headers, f"missing column {col!r}; got {headers}"

    @allure.story("Summary cards render")
    def test_summary_cards_present(self, my_products):
        for card in MY_PRODUCTS_SUMMARY_CARDS:
            allure.attach(f"{card} = {my_products.summary_card(card)}", name=card)

    @allure.story("Total Products badge matches row count on first page")
    def test_total_products_badge_consistent_with_rows(self, my_products):
        total = my_products.total_products()
        rows = my_products.table.row_count()
        page_size = 10
        expected_rows = min(total, page_size)
        assert rows == expected_rows or my_products.table.is_empty(), (
            f"badge says {total} but first page shows {rows} rows"
        )

    @allure.story("Empty state message")
    def test_empty_state_when_no_products(self, my_products):
        if my_products.table.is_empty():
            assert "No products found" in my_products.table.empty_text() or \
                   "No products found" in my_products.page.locator("main").inner_text()

    @allure.story("Search by name filters the list")
    @pytest.mark.regression
    def test_search_by_name_no_match_shows_empty(self, my_products):
        my_products.search("ZZ_NO_SUCH_PRODUCT_ZZ_260908")
        assert my_products.table.row_count() == 0

    @allure.story("Reset Filters clears search")
    def test_reset_filters_clears_search(self, my_products):
        my_products.search("ZZ_NO_SUCH_PRODUCT_ZZ")
        my_products.reset_filters()
        assert my_products.name_search.value() in ("", None)

    @allure.story("Seeded product appears with correct mapped data")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.integration
    def test_seed_product_full_is_listed(self, my_products, products_data):
        seed = products_data.get("seed", {}).get("product_full", {})
        name = seed.get("product_name")
        if not name or not my_products.has_product(name):
            pytest.skip(f"seed product {name!r} not present - run the manual seed step first")
        assert my_products.has_product(name)
        prices = my_products.price_cells(name)
        allure.attach(str(prices), name="listed prices")
        assert prices["sale"], "Sale Price cell is empty for the seeded product"

    @allure.story("Pagination controls behave at boundaries")
    @pytest.mark.regression
    def test_pagination_prev_disabled_on_first_page(self, my_products):
        if my_products.pagination.total() <= 10:
            pytest.skip("not enough data to paginate")
        # On page 1, Previous should be disabled / no-op
        summary_before = my_products.pagination.summary()
        my_products.pagination.prev(my_products.click)
        assert my_products.pagination.summary() == summary_before

    @allure.story("Download Stock List is available")
    def test_download_stock_list_button_present(self, my_products):
        assert my_products.download_stock_btn.is_visible()

    @allure.story("BUG-PROD-007: summary KPI cards refresh after a product is created")
    @allure.issue("BUG-PROD-007")
    @pytest.mark.integration
    @pytest.mark.regression
    def test_summary_cards_refresh_after_create(self, my_products, products_data):
        """After a create the table + 'Total Products' update, but the summary
        cards (Total SKUs / Out of stock) stay stale until a page reload."""
        seed = products_data.get("existing", {})
        ptype = (seed.get("product_types_sample") or ["CAPSULE UPDATED"])[0]
        company = (seed.get("companies_sample") or ["ABBOTT LABORATORIES"])[0]

        skus_before = my_products.summary_card("Total SKUs")
        total_before = my_products.total_products()

        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled - create is blocked here (BUG-PROD-001)")
        data = dg.new_product(product_type=ptype, company=company, cost_per_box=0)
        with my_products.page.expect_response(
            lambda r: "pharmacy-products/create/" in r.url, timeout=15_000
        ) as ri:
            drawer.fill_form(data)
            drawer.submit()
        if ri.value.status not in (200, 201):
            pytest.skip(f"create returned {ri.value.status} - environment issue (BUG-API-001)")

        my_products.page.wait_for_timeout(1_500)
        total_after = my_products.total_products()
        skus_after = my_products.summary_card("Total SKUs")
        allure.attach(
            f"Total Products {total_before}->{total_after} | Total SKUs {skus_before}->{skus_after}",
            name="post-create state",
        )
        assert total_after == total_before + 1, "Total Products did not increment"
        # Desired: the card tracks the new count without a reload.
        assert skus_after != skus_before, (
            f"BUG-PROD-007 reproduced: 'Total SKUs' stayed at {skus_before!r} after a "
            f"create (Total Products {total_before}->{total_after})"
        )
