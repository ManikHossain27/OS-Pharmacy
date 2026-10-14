"""Barcode Generator - table of My-Products rows, bulk qty, per-row barcode count.

Rewritten 2026-09-09 to match the real build: this screen is a TABLE (not a
multi-select + Generate button).  See pages/barcode_generator_page.py.

The per-row printer icon opens Chrome's NATIVE print dialog (BUG-BARCODE-001) and
would block an unattended run, so these tests assert on its presence / on the
absence of an in-app preview but never click it.
"""
from __future__ import annotations

import allure
import pytest

pytestmark = [pytest.mark.products]


@allure.epic("Products")
@allure.feature("Barcode Generator")
class TestBarcodeGenerator:

    @allure.story("Page loads as a product table with the expected controls")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_page_loads(self, barcode_generator):
        bg = barcode_generator
        assert bg.page.locator("table").first.is_visible()
        for label in ("Product Details", "Barcode", "Stock Qty", "Print Qty"):
            assert label in bg.table.headers(), f"missing column {label!r}"
        assert bg.reset_btn.is_visible()
        assert bg.fill_from_stock_btn.is_visible()

    @allure.story("Search filters the product table")
    @pytest.mark.regression
    def test_search_filters_rows(self, barcode_generator):
        bg = barcode_generator
        names = bg.row_names()
        if not names:
            pytest.skip("no products in this pharmacy to search")
        token = names[0].split()[0]
        bg.search(token)
        bg.page.wait_for_url(f"**productName={token}**", timeout=6_000)
        assert all(token.lower() in n.lower() for n in bg.row_names()), (
            f"search {token!r} returned non-matching rows: {bg.row_names()}"
        )

    @allure.story("'Per row barcode' offers counts 1..6")
    @pytest.mark.ui
    def test_per_row_barcode_options(self, barcode_generator):
        opts = [o.strip() for o in barcode_generator.per_row_barcode_options()]
        assert opts == ["1", "2", "3", "4", "5", "6"], f"unexpected options: {opts}"

    @allure.story("Apply is disabled until a row is selected AND a qty is entered")
    @pytest.mark.regression
    def test_apply_requires_selection_and_qty(self, barcode_generator):
        bg = barcode_generator
        names = bg.row_names()
        if not names:
            pytest.skip("no products to select")
        assert not bg.apply_enabled(), "Apply should start disabled"
        bg.select_row(names[0])
        assert not bg.apply_enabled(), "Apply should still be disabled with no qty"
        bg.set_all_selected_qty(5)
        assert bg.apply_enabled(), "Apply should enable once a row + a qty exist"

    @allure.story("'Set all selected item qty' + Apply updates only the checked rows")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    def test_apply_qty_to_selected_only(self, barcode_generator):
        bg = barcode_generator
        names = bg.row_names()
        if len(names) < 2:
            pytest.skip("need >= 2 products")
        target, other = names[0], names[1]
        bg.select_row(target)
        bg.apply_qty_to_selected(5)
        assert bg.print_qty(target) == "5", f"selected row Print Qty not applied ({bg.print_qty(target)})"
        assert bg.print_qty(other) == "1", f"unselected row Print Qty changed ({bg.print_qty(other)})"

    @allure.story("Print Qty cannot go below 1")
    @pytest.mark.boundary
    def test_print_qty_min_is_one(self, barcode_generator):
        bg = barcode_generator
        names = bg.row_names()
        if not names:
            pytest.skip("no products")
        bg.set_print_qty(names[0], -3)
        raw = bg.print_qty(names[0])
        assert not raw.startswith("-") and raw not in ("0", ""), (
            f"Print Qty accepted an out-of-range value: {raw!r}"
        )

    @allure.story("BUG-BARCODE-001: no in-app label preview; the printer icon calls the native dialog")
    @allure.issue("BUG-BARCODE-001")
    @pytest.mark.ui
    def test_no_in_app_preview_before_print(self, barcode_generator):
        bg = barcode_generator
        names = bg.row_names()
        if not names:
            pytest.skip("no products")
        # The printer icon exists per row...
        assert bg.row_print_icon(names[0]).count() == 1
        # ...but there is no in-app preview of the label to check first.
        assert not bg.has_in_app_preview(), (
            "an in-app barcode preview appeared - BUG-BARCODE-001 may be fixed; re-verify the print flow"
        )
        # NOTE: intentionally NOT clicking the icon - it opens the native print
        # dialog (BUG-BARCODE-001) which blocks the browser tab.
