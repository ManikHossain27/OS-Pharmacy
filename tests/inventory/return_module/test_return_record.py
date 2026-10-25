"""Inventory Return Record (route /inventory-return-record): the list of completed returns, its summary tiles, filters,
Return Details and the row menu. Read-only: it works on the returns the other modules of this suite (and earlier runs)
created; each test skips itself when the list is empty."""
from __future__ import annotations

import re

import allure
import pytest

from pages.inventory_return_page import OPTION, InventoryReturnRecordPage
from tests.inventory.return_module.helpers import TOL, detail

ROUND = pytest.approx


@pytest.fixture()
def rec(page, pool) -> InventoryReturnRecordPage:
    """The Inventory Return Record with at least one return on it."""
    r = InventoryReturnRecordPage(page).open()
    if r.row_count() == 0:
        pytest.skip("no returns yet")
    return r


def _single_page(rec) -> bool:
    text = re.sub(r"\s+", " ", rec.page.locator("body").inner_text())
    m = re.search(r"Showing \d+-\d+ of (\d+)", text)
    return bool(m) and int(m.group(1)) == rec.row_count()


@allure.epic("Inventory")
@allure.feature("Inventory Return Record")
class TestReturnRecordList:
    @allure.story("The list has the documented columns")
    def test_columns(self, rec):
        heads = [h.strip() for h in rec.page.locator("thead th").all_inner_texts()]
        assert heads[:7] == ["Return Id / Date", "Supplier Info", "Return Qty", "Return Price", "Demurrage", "Status",
                             "Updated By"], heads

    @allure.story("Rows are listed newest first")
    def test_newest_first(self, rec):
        ids = [r["id"] for r in rec.all_rows()]
        assert ids == sorted(ids, reverse=True), ids

    @allure.story("Every row has an id, date, supplier with phone, item count, price, status and the updating user")
    def test_row_fields(self, rec):
        for r in rec.all_rows():
            assert re.match(r"INV_\d{8}_\d+", r["id"]) and r["date"] and r["supplier"] and r["phone"], r
            assert re.match(r"\d+ items?", r["items"]) and r["status"] in ("Returned", "Cancelled") and r["updated_by"], r

    @allure.story("Total Returns equals the sum of the Returned rows (cancelled returns excluded)")
    @pytest.mark.negative
    def test_tiles_match_rows(self, rec):
        if not _single_page(rec):
            pytest.skip("rows span several pages")
        returned = [r for r in rec.all_rows() if r["status"] == "Returned"]
        tiles = rec.summary()
        assert tiles["returns_count"] == len(returned), (tiles, len(returned))
        assert tiles["returns_total"] == ROUND(sum(r["price"] for r in returned), abs=1.01)

    @allure.story("The Total Demurrage tile's count badge counts the returns that carry demurrage")
    @pytest.mark.negative
    def test_demurrage_badge(self, rec):
        if not _single_page(rec):
            pytest.skip("rows span several pages")
        rows = [r for r in rec.all_rows() if r["status"] == "Returned"]
        with_dem = [r for r in rows if r["demurrage"].strip() not in ("-", "")]
        assert rec.summary()["demurrage_count"] == len(with_dem), (rec.summary(), len(with_dem))

    @allure.story("A return without demurrage shows '-' in the Demurrage column")
    def test_no_demurrage_dash(self, rec):
        plain = [r for r in rec.all_rows() if r["status"] == "Returned" and r["demurrage"].strip() in ("-", "")]
        if not plain:
            pytest.skip("every return has demurrage")
        assert all(r["demurrage"].strip() == "-" for r in plain)

    @allure.story("Return Details open for a row with the supplier, pricing breakdown and items")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_details_content(self, rec):
        first = rec.first_row()
        text = rec.open_details(rec.rows.first)
        for label in ("Inventory ID", "Supplier Name", "Total Items", "Total Return Value", "Final Price", "Status",
                      "Inventory Items"):
            assert label in text, label
        assert first["id"] in detail(text, "Inventory ID") and first["supplier"] in detail(text, "Supplier Name")
        assert detail(text, "Status") == first["status"]

    @allure.story("The Final Price in Return Details equals the Return Price on the list")
    def test_details_price_matches_list(self, rec):
        first = rec.first_row()
        text = rec.open_details(rec.rows.first)
        m = re.search(r"Final Price[^\n]*\n\s*Tk\s*([\d,.]+)", text)
        assert m and float(m.group(1).replace(",", "")) == ROUND(first["price"], abs=TOL), text[:700]

    @allure.story("Return Details line items show quantity, purchase price, demurrage and price per line")
    def test_details_line_items(self, rec):
        text = rec.open_details(rec.rows.first)
        items = text[text.index("Inventory Items"):]
        assert re.search(r"Tk\s*[\d.,]+", items) and ("pc" in items or "box" in items), items[:600]
        assert not re.search(r"\b0\s*box\s*/?\s*0\s*pc\b", items), "BUG-INV-022: line quantity shows 0 box / 0 pc"

    @allure.story("A Returned row offers View Details and Cancel Return")
    def test_row_menu_returned(self, rec):
        idx = next((i for i, r in enumerate(rec.all_rows()) if r["status"] == "Returned"), None)
        if idx is None:
            pytest.skip("no Returned row")
        assert rec.menu_items(rec.rows.nth(idx)) == ["View Details", "Cancel Return"]

    @allure.story("Showing x-y of n is consistent with the rows on the page")
    def test_showing_range(self, rec):
        text = re.sub(r"\s+", " ", rec.page.locator("body").inner_text())
        m = re.search(r"Showing (\d+)-(\d+) of (\d+)", text)
        assert m, text[-300:]
        assert int(m.group(2)) - int(m.group(1)) + 1 == rec.row_count()


@allure.epic("Inventory")
@allure.feature("Inventory Return Record")
class TestReturnRecordFilters:
    @allure.story("The supplier filter narrows the list to that supplier")
    def test_supplier_search(self, rec):
        name = rec.first_row()["supplier"]
        rec.search_supplier(name)
        rows = rec.all_rows()
        assert rows and all(name.lower() in r["supplier"].lower() for r in rows), rows

    @allure.story("Search by return id finds exactly that return; an unknown text shows an empty list")
    @pytest.mark.negative
    def test_text_search(self, rec):
        first = rec.first_row()["id"]
        rec.search_text(first)
        assert [r["id"] for r in rec.all_rows()] == [first]
        rec.search_text("zzz-no-such-return")
        assert rec.row_count() == 0

    @allure.story("Status filter: Returned shows only Returned rows")
    def test_status_returned(self, rec):
        rec.choose_status("Returned")
        rows = rec.all_rows()
        assert rows and all(r["status"] == "Returned" for r in rows)

    @allure.story("Status filter: Cancelled shows only Cancelled rows")
    def test_status_cancelled(self, rec):
        rec.choose_status("Cancelled")
        assert all(r["status"] == "Cancelled" for r in rec.all_rows())

    @allure.story("Reset Filters restores the full list")
    def test_reset(self, rec):
        full = rec.row_count()
        rec.search_text("zzz-no-such-return")
        rec.reset_filters()
        assert rec.row_count() == full

    @allure.story("Updated By lists the staff who made returns")
    def test_updated_by_options(self, rec):
        rec.page.locator(".ant-select", has_text="All staff").first.click()
        rec.page.wait_for_timeout(800)
        opts = [o.strip() for o in rec.page.locator(OPTION).all_inner_texts()]
        rec.page.keyboard.press("Escape")
        assert rec.first_row()["updated_by"] in opts, opts
