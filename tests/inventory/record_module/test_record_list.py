"""Inventory Record list (spec section 43) - layout, filters, search, paging, row content, details link.

READ-ONLY: nothing is created.  Findings probed live 2026-10-12:
  * the list request always carries ``from`` / ``to`` = the current day although the Date Range inputs show blank;
  * Status = Paid / Due / Advance makes the list request fail with HTTP 400 (BUG-INV-034).
"""
from __future__ import annotations

import re
from datetime import datetime

import allure
import pytest

from utils.helpers import money

pytestmark = [pytest.mark.inventory, pytest.mark.regression]

# spec "Inventory Type and Supplier Payment": two types, Purchase and Borrow (Missing / Destroyed are Stock Adjustment types)
TYPES = ["Purchase", "Borrowed"]
STATUSES = ["Paid", "Due", "Advance", "Returned", "Cancelled"]
COLUMNS = ["Inventory Id/Created Date", "Supplier Info", "Type", "Qty", "Bill Amount", "Paid Amount", "Status",
           "Received By", "Actions"]
ID_RE = re.compile(r"^#INV_\d{8}_\d+$")


def _ids(record) -> list[str]:
    return [v["id"] for v in record.all_row_values()]


@allure.epic("Inventory")
@allure.feature("Inventory Record - layout (spec 43)")
class TestLayout:

    @allure.story("Heading, summary tiles, filters and the table columns are present")
    @pytest.mark.smoke
    def test_layout(self, record):
        text = record.page.locator("main").inner_text()
        for label in ("Total Inventory", "Total Paid", "Total Due", "Total Discount", "Product", "Date Range",
                      "Supplier", "Inventory Type", "Status"):
            assert label in text, f"{label!r} missing on the Inventory Record page"
        assert [h for h in record.table.headers() if h] == COLUMNS
        assert record.reset_filters_btn.is_visible()

    @allure.story("Summary tiles show 'Total Inventory (N)' with a count and Tk amounts")
    def test_tiles_format(self, record):
        text = record.page.locator("main").inner_text()
        assert re.search(r"Total Inventory \(\d+\)", text)
        for label in ("Total Paid", "Total Due", "Total Discount"):
            assert re.search(rf"{label}\s*\n?\s*Tk\s*[\d,]+", text), f"{label} tile has no Tk amount"

    @allure.story("Filter options: Inventory Type and Status lists as specified by the product")
    def test_filter_options(self, record):
        assert record.filter_options("type") == TYPES
        assert record.filter_options("status") == STATUSES
        assert "jb" in record.filter_options("supplier")


@allure.epic("Inventory")
@allure.feature("Inventory Record - filters (spec 43)")
class TestFilters:

    @pytest.mark.parametrize("status", STATUSES)
    @allure.story("Status filter returns the records of that status (no request error)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_status_filter(self, record_all, status):
        if status in ("Paid", "Due", "Advance"):
            allure.dynamic.issue("BUG-INV-034")
        resp = record_all.choose_filter("status", status)
        assert resp["status"] == 200, f"Status={status}: list request failed HTTP {resp['status']} {resp['body'][:120]!r}"
        wrong = [v for v in record_all.all_row_values() if v["status"].lower() != status.lower()]
        assert not wrong, f"Status={status}: rows with another status: {wrong[:2]}"

    @pytest.mark.parametrize("typ", TYPES)
    @allure.story("Inventory Type filter returns only that type")
    def test_type_filter(self, record_all, typ):
        resp = record_all.choose_filter("type", typ)
        assert resp["status"] == 200, resp
        rows = record_all.all_row_values()
        wrong = [v for v in rows if v["type"].lower() != typ.lower()]
        assert not wrong, f"Type={typ}: {len(wrong)} of {len(rows)} rows show another type, e.g. {wrong[:1]}"

    @allure.story("Supplier filter returns only that supplier's records")
    def test_supplier_filter(self, record_all):
        resp = record_all.choose_filter("supplier", "jb")
        assert resp["status"] == 200, resp
        rows = record_all.all_row_values()
        assert rows and all(v["supplier"].startswith("jb") for v in rows), rows[:2]

    @allure.story("Search by an unknown name shows the empty state, not an error")
    def test_search_no_match(self, record):
        resp = record._list_response(lambda: record.product_search.search("zzzz-no-such-product"))
        assert resp["status"] == 200 and "searchKey=zzzz-no-such-product" in resp["url"], resp
        assert record.row_count() == 0 and record.table.is_empty()

    @allure.story("Reset Filters clears the status filter and restores the list")
    def test_reset_filters(self, record_all):
        record_all.choose_filter("status", "Returned")
        resp = record_all.reset_filters()
        assert resp["status"] == 200 and "status=" not in resp["url"], f"status still sent after reset: {resp['url']}"
        assert "RETURNED" not in resp["url"]

    @allure.story("Two filters combine: Type AND Supplier")
    def test_combined_filters(self, record_all):
        record_all.choose_filter("type", "Purchase")
        resp = record_all.choose_filter("supplier", "jb")
        assert resp["status"] == 200 and "type=PURCHASE" in resp["url"] and "supplierId=" in resp["url"], resp["url"]
        assert all(v["type"] == "Purchase" and v["supplier"].startswith("jb") for v in record_all.all_row_values())


@allure.epic("Inventory")
@allure.feature("Inventory Record - date range")
class TestDateRange:

    @allure.story("The list is scoped to a date range; the Date Range inputs must show the range that is applied")
    def test_applied_range_is_visible(self, record):
        start = record.page.locator("main input[placeholder='Start date']").input_value()
        end = record.page.locator("main input[placeholder='End date']").input_value()
        resp = record._list_response(lambda: record.page.get_by_placeholder("Search by name").fill("zzzz"))
        has_range = "from=" in resp["url"] and "to=" in resp["url"]
        applied = re.findall(r"from=\d+&to=\d+", resp["url"])
        assert not has_range or (start and end),             f"list request is limited by {applied} but the Date Range shows {start!r} - {end!r}"

    @allure.story("A single-day range lists only records created that day")
    def test_rows_inside_range(self, record_all):
        probe = record_all.all_row_values()[0]["date"]          # e.g. '12 Oct 2026, 03:58 pm'
        day = datetime.strptime(probe.split(",")[0], "%d %b %Y")
        resp = record_all.set_date_range(day.strftime("%Y-%m-%d"), day.strftime("%Y-%m-%d"))
        assert resp["status"] == 200, resp
        dates = [v["date"] for v in record_all.all_row_values()]
        assert dates and all(d.startswith(probe.split(",")[0]) for d in dates), f"rows outside {probe[:11]}: {dates[:3]}"


@allure.epic("Inventory")
@allure.feature("Inventory Record - paging")
class TestPaging:

    @allure.story("Page size options are 10 / 20 / 50 / 100 and each limits the rows shown")
    @pytest.mark.parametrize("size", [10, 20, 50, 100])
    def test_page_size(self, record_all, size):
        assert record_all.page_size_options() == [10, 20, 50, 100]
        total = record_all.footer()[2] if record_all.footer() else 0
        if record_all.page_size() != size:
            record_all.set_page_size(size)
        assert record_all.page_size() == size
        rows = record_all.row_count()
        assert rows == min(size, total), f"page size {size}: {rows} rows for a total of {total}"

    @allure.story("'Showing a-b of N' matches the rows on the page and the total is stable across page sizes")
    def test_footer_matches_rows(self, record_all):
        a, b, total = record_all.footer()
        assert (a, b - a + 1) == (1, record_all.row_count())
        record_all.set_page_size(50)
        a2, b2, total2 = record_all.footer()
        assert total2 == total and b2 == min(50, total)

    @allure.story("Next / Previous move through the list without repeating or losing a record")
    def test_next_previous(self, record_all):
        record_all.set_page_size(10)
        first = _ids(record_all)
        assert record_all.has_next(), "fewer than 11 records in range - nothing to page through"
        record_all.go_next()
        second = _ids(record_all)
        assert second and not set(first) & set(second), "a record appears on two pages"
        record_all.go_prev()
        assert _ids(record_all) == first

    @allure.story("Every page of the list shows distinct, newest-first records")
    def test_all_pages_unique_and_ordered(self, record_all):
        record_all.set_page_size(100)
        seen: list[str] = _ids(record_all)
        guard = 0
        while record_all.has_next() and guard < 10:
            record_all.go_next()
            seen += _ids(record_all)
            guard += 1
        total = record_all.footer()[2] if record_all.footer() else len(seen)
        assert len(seen) == len(set(seen)) == total, f"{len(seen)} rows read, {len(set(seen))} unique, footer says {total}"
        # '#INV_<yyyymmdd>_<n>': the sequence restarts every day, so order by (day, n)
        keys = [(i.split("_")[1], int(i.rsplit("_", 1)[1])) for i in seen]
        assert keys == sorted(keys, reverse=True), "records are not newest first"


@allure.epic("Inventory")
@allure.feature("Inventory Record - row content (spec 43)")
class TestRowContent:

    @allure.story("Every row has a well-formed ID, date, supplier, type, item count, amounts and status")
    def test_row_format(self, record_all):
        rows = record_all.all_row_values()
        assert rows
        for v in rows:
            assert ID_RE.match(v["id"]), v
            assert re.match(r"\d{1,2} [A-Z][a-z]{2} \d{4}, \d{1,2}:\d{2} [ap]m$", v["date"]), v
            assert v["type"] in TYPES, v
            assert re.match(r"\d+ items?$", v["qty"]), v
            assert v["status"] in STATUSES, v
            assert v["supplier"], v
            assert re.search(r"Tk\s*[\d,.]+", v["bill"]) and re.search(r"Tk\s*[\d,.]+", v["paid"]), v

    @allure.story("Status agrees with the amounts: Paid => paid >= bill; Due => paid < bill; Advance => paid > bill")
    def test_status_matches_amounts(self, record_all):
        bad = []
        for v in record_all.all_row_values():
            bill, paid = money(v["bill"].split("\n")[0]), money(v["paid"].split("\n")[0])
            if v["status"] == "Advance":     # the Status cell carries the advance amount ('Advance' / 'Tk 250')
                note = money(v["status_note"]) if v["status_note"] else None
                if note is not None and abs(note - (paid - bill)) > 0.51:
                    bad.append((v["id"], "advance amount", note, paid - bill))
            ok = {"Paid": abs(paid - bill) < 0.51, "Due": paid < bill - 0.49, "Advance": paid > bill + 0.49}.get(v["status"], True)
            if not ok:
                bad.append((v["id"], v["status"], bill, paid))
        assert not bad, f"status/amount mismatches: {bad[:5]}"

    @allure.story("The discount badge under Bill Amount shows the discount AMOUNT and rate, not just the entered rate")
    @allure.issue("BUG-INV-007")
    def test_discount_badge_wording(self, record_all):
        badges = [v["bill"] for v in record_all.all_row_values() if "disc" in v["bill"]]
        flat = [b for b in badges if "%" not in b]
        assert not flat or all(re.search(r"Tk\s*[\d.,]+\s*disc", b) for b in flat), badges[:3]


@allure.epic("Inventory")
@allure.feature("Inventory Record - details link (spec 43 / 44.1)")
class TestDetailsLink:

    @allure.story("The details action opens the same inventory's Details view")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_open_details_matches_row(self, record_all):
        row_id = record_all.row_values(record_all.row(0))["id"]
        dlg = record_all.open_details(0)
        dlg.wait_loaded()
        assert row_id.lstrip("#") in dlg.full_text() or row_id in dlg.full_text(), \
            f"Details for row {row_id} shows {dlg.inventory_id()!r}"
