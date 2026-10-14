"""Inventory Record (route: /inventory-record) - list + "Inventory Details" dialog."""
from __future__ import annotations

import re
import time
from typing import Any

import allure
from playwright.sync_api import Locator, Page, expect

from components.data_table import DataTable
from components.search_field import SearchField
from pages.base_page import BasePage
from utils.constants import ROUTES


class InventoryRecordPage(BasePage):
    route = ROUTES["inventory_record"]

    def __init__(self, page: Page):
        super().__init__(page)
        self.table = DataTable(page)
        self.product_search = SearchField(page, page.get_by_placeholder("Search by name"))
        self.reset_filters_btn = page.get_by_role("button", name="Reset Filters")

    # ------------------------------------------------------------------ loaders
    def open(self) -> "InventoryRecordPage":
        super().open()
        return self.wait_loaded()

    def is_loaded(self) -> bool:
        return self.page.get_by_text("Inventory Record", exact=True).count() > 0

    def wait_loaded(self, timeout: float = 20.0) -> "InventoryRecordPage":
        expect(self.page.get_by_text("Inventory Record", exact=True).first).to_be_visible()
        # The heading renders before the table's async data fetch resolves,
        # and on this page the list can visibly populate in more than one
        # round-trip (row count observed climbing 0 -> 1 -> 4 across successive
        # checks seconds apart) - AntD's ".ant-table-placeholder" ("no data")
        # row also renders TRANSIENTLY while still loading, not only when
        # genuinely empty. So neither "networkidle" nor "any row/placeholder
        # present" is a trustworthy done-signal on its own; wait for the row
        # count to stop changing across consecutive reads instead.
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout * 1000)
        except Exception:
            pass
        # An early transient 0 (or 1) can itself look "stable" for a check or
        # two before more rows stream in, so require several consecutive
        # equal reads spanning ~1.5s, not just two - and never accept 0 as
        # stable unless the placeholder is present (genuinely empty).
        deadline = time.monotonic() + timeout
        last = -1
        streak = 0
        while time.monotonic() < deadline:
            current = self.table.rows.count()
            has_placeholder = self.page.locator(".ant-table-placeholder").count() > 0
            if current == last and (current > 0 or has_placeholder):
                streak += 1
                if streak >= 5:
                    break
            else:
                streak = 0
            last = current
            time.sleep(0.3)
        return self

    # ------------------------------------------------------------------ summary tiles
    def summary_tile(self, label: str) -> str:
        return self.page.get_by_text(label, exact=True).locator("xpath=following-sibling::*[1]").inner_text().strip()

    # ------------------------------------------------------------------ list
    def search_product(self, term: str) -> None:
        self.product_search.search(term)

    def row_count(self) -> int:
        return self.table.row_count()

    def row(self, index: int) -> Locator:
        return self.table.rows.nth(index)

    def row_by_inventory_id(self, inventory_id: str) -> Locator:
        return self.table.row_by_text(inventory_id)

    def bill_amount_cell_text(self, row: Locator) -> str:
        return row.locator("td").nth(4).inner_text().strip()

    def paid_amount_cell_text(self, row: Locator) -> str:
        return row.locator("td").nth(5).inner_text().strip()

    def status_cell_text(self, row: Locator) -> str:
        return row.locator("td").nth(6).inner_text().strip()

    def _row_action(self, row: Locator, index: int) -> Locator:
        return row.locator("td").last.locator("div[style*='cursor: pointer']").nth(index)

    # ------------------------------------------------------------------ filters / paging (live-probed 2026-10-12)
    FILTERS = {"supplier": 0, "type": 1, "status": 2}      # order of the three AntD selects under the tiles

    def _filter_select(self, kind: str) -> Locator:
        return self.page.locator("main .ant-select").nth(self.FILTERS[kind])

    def _list_response(self, trigger) -> dict:
        """Run ``trigger`` and return {url, status, body} of the list request it causes."""
        with self.page.expect_response(
                lambda r: "/inventories/" in r.url and "/inventories/id/" not in r.url
                and r.request.method == "GET" and "page=" in r.url, timeout=30_000) as info:
            trigger()
        r = info.value
        try:
            body = r.text()[:400]
        except Exception:
            body = ""
        self.page.wait_for_timeout(900)
        return {"url": r.url, "status": r.status, "body": body}

    _OPEN_DROPDOWN = ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"

    def _close_dropdowns(self) -> None:
        """Close any open select and wait until no dropdown is left (a closing one still matches ':visible')."""
        self.page.keyboard.press("Escape")
        self.page.wait_for_function(
            "() => !document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')", timeout=5_000)

    def _open_dropdown(self, kind: str) -> Locator:
        self._close_dropdowns()
        self._filter_select(kind).click()
        dd = self.page.locator(self._OPEN_DROPDOWN)
        dd.first.wait_for(state="visible")
        self.page.wait_for_timeout(400)
        return dd.last

    def filter_options(self, kind: str) -> list[str]:
        dd = self._open_dropdown(kind)
        opts = [o.strip() for o in dd.locator(".ant-select-item-option").all_inner_texts()]
        self._close_dropdowns()
        return opts

    @allure.step("Filter {kind} = {option}")
    def choose_filter(self, kind: str, option: str) -> dict:
        def _do():
            dd = self._open_dropdown(kind)
            dd.locator(".ant-select-item-option").filter(has_text=re.compile(rf"^{re.escape(option)}$")).click()
        return self._list_response(_do)

    @allure.step("Date Range {start} - {end}")
    def set_date_range(self, start: str, end: str) -> dict:
        """Type ``start`` / ``end`` (YYYY-MM-DD, the picker's display format); returns the last list response."""
        box = self.page.locator("main .ant-picker").first
        s_in = box.locator("input").nth(0)
        e_in = box.locator("input").nth(1)
        s_in.click()
        s_in.fill(start)
        s_in.press("Enter")
        self.page.wait_for_timeout(300)
        return self._list_response(lambda: (e_in.fill(end), e_in.press("Enter")))

    @allure.step("Reset Filters")
    def reset_filters(self) -> dict:
        return self._list_response(self.reset_filters_btn.click)

    def footer(self) -> tuple[int, int, int] | None:
        """(first, last, total) of 'Showing a-b of N', or None when the table is empty / has no footer."""
        m = re.search(r"Showing\s+(\d+)\s*-\s*(\d+)\s+of\s+(\d+)", self.page.locator("main").inner_text())
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

    def page_size(self) -> int:
        return int(self.page.locator(".table-footer-page-size-select").inner_text().split()[0])

    def page_size_options(self) -> list[int]:
        sel = self.page.locator(".table-footer-page-size-select")
        sel.click()
        self.page.wait_for_timeout(500)
        opts = [int(o.split()[0]) for o in
                self.page.locator(".ant-select-dropdown:visible .ant-select-item-option").all_inner_texts()]
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(250)
        return opts

    @allure.step("Set page size {size}")
    def set_page_size(self, size: int) -> dict:
        def _do():
            self.page.locator(".table-footer-page-size-select").click()
            self.page.wait_for_timeout(400)
            self.page.locator(".ant-select-dropdown:visible .ant-select-item-option").filter(
                has_text=re.compile(rf"^{size}\b")).click()
        return self._list_response(_do)

    def go_next(self) -> dict:
        return self._list_response(self.page.locator(".ant-pagination-next").click)

    def go_prev(self) -> dict:
        return self._list_response(self.page.locator(".ant-pagination-prev").click)

    def go_to_page(self, n: int) -> dict:
        return self._list_response(self.page.locator(f".ant-pagination-item-{n}").click)

    def has_next(self) -> bool:
        nxt = self.page.locator(".ant-pagination-next")
        return nxt.count() > 0 and "ant-pagination-disabled" not in (nxt.get_attribute("class") or "")

    def row_values(self, row: Locator) -> dict[str, str]:
        tds = row.locator("td").all_inner_texts()
        first = [t.strip() for t in tds[0].split("\n") if t.strip()]
        return {"id": first[0] if first else "", "date": first[1] if len(first) > 1 else "",
                "supplier": " ".join(t.strip() for t in tds[1].split("\n") if t.strip()),
                "type": tds[2].strip(), "qty": tds[3].strip(), "bill": tds[4].strip(),
                "paid": tds[5].strip(), "status": tds[6].strip().splitlines()[0].strip() if tds[6].strip() else "",
                "status_note": " ".join(tds[6].split()[1:]), "received_by": tds[7].strip()}

    def all_row_values(self) -> list[dict[str, str]]:
        return [self.row_values(self.row(i)) for i in range(self.row_count())]

    @allure.step("Open Inventory Details for row {index}")
    def open_details(self, index: int = 0) -> "InventoryDetailsDialog":
        row = self.row(index)
        dlg = InventoryDetailsDialog(self.page)
        self.click(self._row_action(row, 0), expect_effect=dlg.is_open, description="open Inventory Details")
        return dlg

    @allure.step("Open Inventory Details for row {index}, capturing the raw API response")
    def open_details_capturing_api(self, index: int = 0) -> tuple["InventoryDetailsDialog", dict]:
        """Same as open_details() but also captures the body of the GET
        .../inventories/id/{id}/{pharmacyId} response that the drawer itself
        triggers - used to prove/disprove BUG-INV-021 (a per-product discount
        allocation is never computed or persisted server-side at all, so the
        Inventory Details 'Discount' column has no data to render regardless
        of whether the column itself exists in the UI)."""
        result: dict[str, Any] = {}

        def _capture(resp) -> None:
            if "/inventories/id/" in resp.url and resp.request.method == "GET":
                try:
                    result["body"] = resp.json()
                except Exception:
                    pass

        row = self.row(index)
        dlg = InventoryDetailsDialog(self.page)
        self.page.on("response", _capture)
        try:
            self.click(self._row_action(row, 0), expect_effect=dlg.is_open, description="open Inventory Details")
            self.page.wait_for_timeout(500)
        finally:
            self.page.remove_listener("response", _capture)
        return dlg, result.get("body", {})


class InventoryDetailsDialog:
    """Inventory Details. NOTE: it is a PAGE (``/inventory-record/details/<id>``), not a dialog or
    drawer - verified live 2026-10-07. The class name is kept for the existing tests.

    Rendered labels (Default mode):
      header   : Inventory ID | Inventory Mode | Supplier Name | Supplier Phone Number |
                 Inventory Date & Time | Received By
      pricing  : Total Items | Total Price (TP+VAT) | General Discount | Special Discount |
                 Round Off | Final Price | Total Paid (+ one row per payment method) | Payment Status
      items    : Details | Batch / Expiry | Rack No | Qty | Qty/Box | BTP+VAT | Discount |
                 Purchase Price | Retail Price | Wholesale Price | Margin | Price
    """

    HEADER_FIELDS = ["Inventory ID", "Inventory Mode", "Supplier Name", "Supplier Phone Number",
                     "Inventory Date & Time", "Received By"]
    PRICING_FIELDS = ["Total Items", "Total Price (TP+VAT)", "Total TP", "Total VAT", "General Discount",
                      "General Discount (on TP)", "Special Discount", "Less", "Round Off", "Final Price", "Total Paid",
                      "Payment Status"]        # Total TP / Total VAT / '(on TP)' exist in TP/VAT mode only
    ITEM_COLUMNS = ["Details", "Batch / Expiry", "Rack No", "Qty", "Qty/Box", "BTP+VAT", "Discount",
                    "Purchase Price", "Retail Price", "Wholesale Price", "Margin", "Price"]

    # What the Details page must show (spec 44.1 as clarified by the user 2026-10-07):
    #   * Min. Qty and Barcode are NOT required on this view.
    #   * "Total Price" is shown in the Price column under the "Total:" label (next to "Final:").
    PRICING_BREAKDOWN_REQUIRED_FIELDS = [
        "Total Items", "Total Price (TP+VAT)", "General Discount", "Final Price", "Total Paid", "Payment Status",
    ]
    ITEMS_TABLE_REQUIRED_COLUMNS = [
        "Details", "Batch / Expiry", "Qty", "Qty/Box", "BTP+VAT", "Discount", "Purchase Price",
        "Retail Price", "Wholesale Price", "Price",
    ]
    FREE_QTY_SHOWN_AS = "Free"          # not a column: free pieces must be visible somewhere in the line (see check_details_free)

    def __init__(self, page: Page):
        self.page = page
        self.root = page.locator(".page-content").filter(has=page.get_by_text("Inventory ID", exact=True))
        self.items_table = DataTable(page, root=self.root)

    def is_open(self) -> bool:
        return "/inventory-record/details/" in self.page.url and self.root.count() > 0

    def wait_loaded(self, timeout: int = 30_000) -> "InventoryDetailsDialog":
        """The URL changes before the API data renders: wait for the Inventory ID label and >= 1 item row."""
        expect(self.root.get_by_text("Inventory ID", exact=True).first).to_be_visible(timeout=timeout)
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline and self.items_table.row_count() == 0:
            time.sleep(0.3)
        return self

    def _value(self, label: str) -> str:
        loc = self.root.get_by_text(label, exact=True).first.locator("xpath=following-sibling::*[1]")
        return loc.inner_text().strip()

    def has_label(self, label: str) -> bool:
        return self.root.get_by_text(label, exact=True).count() > 0

    def page_text(self) -> str:
        """Everything the page renders (used to attach evidence and to look for Due / Less / Advance labels)."""
        return self.root.first.inner_text()

    def labelled_amount(self, *labels: str) -> float | None:
        """First rendered label among ``labels`` -> the amount next to it; None when none is shown."""
        from utils.helpers import money
        for label in labels:
            if self.has_label(label):
                try:
                    return money(self._value(label))
                except Exception:
                    continue
        return None

    def inventory_id(self) -> str:
        return self._value("Inventory ID")

    def total_price(self) -> str:
        return self._value("Total Price (TP+VAT)")

    def final_price(self) -> str:
        return self._value("Final Price")

    def total_paid(self) -> str:
        return self._value("Total Paid")

    def payment_status(self) -> str:
        return self._value("Payment Status")

    def pricing_breakdown(self) -> dict[str, str]:
        """{label: value text} for every header / pricing label that is rendered."""
        self.wait_loaded()
        out: dict[str, str] = {}
        for label in self.HEADER_FIELDS + self.PRICING_FIELDS:
            if self.has_label(label):
                try:
                    out[label] = self._value(label)
                except Exception:
                    pass
        return out

    def item_rows(self) -> list[dict[str, str]]:
        """Every line item as {column header: cell text}."""
        self.wait_loaded()
        headers = self.items_table.headers()
        rows = []
        for i in range(self.items_table.row_count()):
            cells = self.items_table.rows.nth(i).locator("td").all_inner_texts()
            rows.append({h: c.strip() for h, c in zip(headers, cells) if h})
        return rows

    def item_headers(self) -> list[str]:
        self.wait_loaded()
        return [h for h in self.items_table.headers() if h]

    def item_row_by_batch(self, batch: str) -> dict[str, str] | None:
        for r in self.item_rows():
            if any(batch in v for v in r.values()):
                return r
        return None

    def item_row(self, index: int) -> Locator:
        return self.items_table.rows.nth(index)

    def item_purchase_price_text(self, index: int) -> str:
        return self.item_rows()[index].get("Purchase Price", "")

    def item_total_price_text(self, index: int) -> str:
        return self.item_rows()[index].get("Price", "")

    def missing_pricing_breakdown_fields(self) -> list[str]:
        return [f for f in self.PRICING_BREAKDOWN_REQUIRED_FIELDS if not self.has_label(f)]

    def missing_item_columns(self) -> list[str]:
        headers = self.item_headers()
        return [c for c in self.ITEMS_TABLE_REQUIRED_COLUMNS if c not in headers]

    def full_text(self) -> str:
        return self.root.inner_text()

    def close(self) -> None:
        """Leave the details page (it has no close button - go back to the Inventory Record list)."""
        self.page.go_back()
        self.page.wait_for_url(lambda u: "/inventory-record/details/" not in u, timeout=30_000)
