"""Sale Record (SRS 7.1): list, search, status filter, tiles, details, edit, cancel.

Tests sell first so the day always has sales. ``allure.issue`` marks the bugs the failing ones document.
"""
from __future__ import annotations

import allure
import pytest

from tests.sale.helpers import sell

pytestmark = [pytest.mark.sale, pytest.mark.regression]


def _stock(sale, term: str) -> int:
    return int(sale.open().stock_in_dropdown(term)[0])


@allure.epic("Sale")
@allure.feature("Sale Record")
class TestSaleRecord:

    @allure.story("BUG-SALE-047: the default view must not hide today's sales behind an unlabelled date filter")
    @allure.issue("BUG-SALE-047")
    def test_default_view_lists_sales_when_tiles_show_sales(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout)
        sale_record.open()
        tiles = sale_record.tiles()
        assert sale_record.row_count() > 0, "the grid is empty right after a sale"
        assert tiles["sales"] > 0

    @allure.story("BUG-SALE-018: searching the invoice number finds the sale (walk-in sales included)")
    @allure.issue("BUG-SALE-018")
    def test_search_finds_walk_in_sale_by_invoice(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout)
        top = sale_record.open().top_row()
        sale_record.search(top.sale_id)
        ids = [r.sale_id for r in sale_record.all_rows()]
        assert top.sale_id in ids, f"searching {top.sale_id!r} returned {ids}"

    @allure.story("BUG-SALE-048: the Paid status filter lists the Paid sales")
    @allure.issue("BUG-SALE-048")
    def test_status_filter_paid_lists_paid_sales(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout)
        sale_record.open().choose_status("Paid")
        rows = sale_record.all_rows()
        assert rows, "the Paid filter returned no rows although a Paid sale exists"
        assert all(r.status == "Paid" for r in rows), [r.status for r in rows]

    @allure.story("Guard: the Cancelled status filter lists cancelled sales")
    def test_status_filter_cancelled_lists_cancelled_sales(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout)
        sale_record.open().cancel_row(0)
        sale_record.open().choose_status("Cancelled")
        rows = sale_record.all_rows()
        assert rows and all(r.status == "Cancelled" for r in rows), [r.status for r in rows]

    @allure.story("BUG-SALE-010: a cancelled sale leaves the Sale Record tiles")
    @allure.issue("BUG-SALE-010")
    def test_cancelled_sale_leaves_the_tiles(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout)
        with_sale = sale_record.open().tiles()
        sale_record.cancel_row(0)
        after = sale_record.open().tiles()
        assert after["sales"] == with_sale["sales"] - 1, f"tiles {with_sale['sales']} -> {after['sales']} after a cancel"

    @allure.story("BUG-SALE-015: View Details shows the batch / expiry used by each line")
    @allure.issue("BUG-SALE-015")
    def test_details_show_batch_and_expiry(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout)
        text = sale_record.open().open_details(0).details_text().lower()
        assert "batch" in text and "expiry" in text, "no batch / expiry in Sale Details"

    @allure.story("TC-SALE-SR-10: cancelling a sale puts the stock back")
    def test_cancel_restores_stock(self, sale, checkout, sale_record, default_config):
        from tests.sale.conftest import PRODUCT
        before = _stock(sale, PRODUCT.lower())
        sell(sale, checkout, qty=2)
        assert _stock(sale, PRODUCT.lower()) == before - 2, "set-up: the sale should take 2 pieces"
        sale_record.open().cancel_row(0)
        assert _stock(sale, PRODUCT.lower()) == before

    @allure.story("TC-SALE-SR-07: editing the quantity updates the bill")
    def test_edit_quantity_updates_the_bill(self, sale, checkout, sale_record, default_config):
        sell(sale, checkout, qty=2)                                  # Tk 100
        sale_record.open()
        toast = sale_record.edit_first_line_qty(0, 1)
        assert "updated" in toast.lower(), f"edit failed: {toast!r}"
        assert sale_record.open().top_row().bill == pytest.approx(50.0)
