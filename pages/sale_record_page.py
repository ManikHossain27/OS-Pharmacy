"""Sale Record (route /sale-record): the list of sales. Columns: Sale Id/Date, Customer Info, Qty, Bill Amount, Paid Amount,
Status, Sold By, Profit, Action. Newest sale first. (The search box does not find walk-in sales by invoice number -
BUG-SALE-018 - so tests read the top row instead.)"""
from __future__ import annotations

import re
from dataclasses import dataclass

import allure

from pages.base_page import BasePage

ROWS = "main tbody tr.ant-table-row"


def _first_number(text: str) -> float | None:
    m = re.search(r"-?[\d,]+(?:\.\d+)?", (text or "").replace("Tk", ""))
    return float(m.group().replace(",", "")) if m else None


@dataclass
class SaleRow:
    sale_id: str
    customer: str
    bill: float | None
    paid: float | None
    status: str
    raw: str


class SaleRecordPage(BasePage):
    ROUTE = "/sale-record"

    def __init__(self, page):
        super().__init__(page)

    @allure.step("Open Sale Record")
    def open(self, route: str | None = None) -> "SaleRecordPage":
        self.page.goto(self.ROUTE)
        self.page.locator(ROWS).first.wait_for(state="visible", timeout=120_000)
        self.page.wait_for_timeout(2_000)
        return self

    def row_count(self) -> int:
        return self.page.locator(ROWS).count()

    def row(self, index: int = 0) -> SaleRow:
        tr = self.page.locator(ROWS).nth(index)
        cells = [c.strip() for c in tr.locator("td").all_inner_texts()]
        return SaleRow(sale_id=cells[0].splitlines()[0].lstrip("#"), customer=cells[1].splitlines()[0],
                       bill=_first_number(cells[3]), paid=_first_number(cells[4]),
                       status=cells[5].splitlines()[0] if cells[5] else "", raw=" | ".join(c.replace("\n", " ") for c in cells))

    def top_row(self) -> SaleRow:
        return self.row(0)

    def open_row_action(self, index: int, action: str) -> "SaleRecordPage":
        """Open the Actions menu of a row and click an item ('View Details', 'Edit Sale', 'Return Sale', 'Cancel Sale', ...)."""
        self.page.locator(ROWS).nth(index).locator(".ant-dropdown-trigger").last.click()
        self.page.locator(".ant-dropdown:not(.ant-dropdown-hidden) li").filter(has_text=action).first.click()
        return self

    # ------------------------------------------------------------------ filters, tiles, paging
    def set_dates(self, start: str, end: str) -> "SaleRecordPage":
        """Both pickers, as YYYY-MM-DD (the grid otherwise shows only 'today' - see BUG-SALE-047)."""
        for box, value in ((self.page.get_by_placeholder("Start date"), start), (self.page.get_by_placeholder("End date"), end)):
            box.click()
            box.fill(value)
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(800)
        self.page.wait_for_timeout(5_000)
        return self

    def date_box_values(self) -> tuple[str, str]:
        return (self.page.get_by_placeholder("Start date").input_value(), self.page.get_by_placeholder("End date").input_value())

    def choose_status(self, label: str) -> "SaleRecordPage":
        """Status filter option: Paid, Due, Cancelled or Returned."""
        self.page.locator("main .ant-select").filter(has_text=re.compile("Search by status|Paid|Due|Cancelled|Returned")).first.click()
        self.page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option").filter(has_text=label).first.click()
        self.page.wait_for_timeout(5_000)
        return self

    def search(self, text: str) -> "SaleRecordPage":
        box = self.page.get_by_placeholder("Search by sale id or customer")
        box.fill(text)
        box.press("Enter")
        self.page.wait_for_timeout(6_000)
        return self

    def all_rows(self) -> list[SaleRow]:
        return [self.row(i) for i in range(self.row_count())]

    def tiles(self) -> dict[str, float]:
        """{'sales': count, 'sales_amount', 'collected', 'profit', 'due'} from the four tiles."""
        text = self.page.locator("main").inner_text()
        count = re.search(r"Total Sales\s*\((\d+)\)", text)

        def amount(label: str) -> float | None:
            m = re.search(label + r"\s*Tk\s*([\d,]+(?:\.\d+)?)", text)
            return float(m.group(1).replace(",", "")) if m else None

        return {"sales": int(count.group(1)) if count else -1, "sales_amount": amount(r"Total Sales\s*\(\d+\)"),
                "collected": amount("Total Collected"), "profit": amount("Total Profit"), "due": amount("Total Due")}

    def footer_total(self) -> int:
        m = re.search(r"Showing\s*\d+\s*-\s*\d+\s*of\s*(\d+)", self.page.locator("main").inner_text())
        return int(m.group(1)) if m else -1

    # ------------------------------------------------------------------ details drawer
    def details_text(self) -> str:
        return self.page.locator("[role=dialog]:visible").last.inner_text()

    def details_items(self) -> list[list[str]]:
        """Sale Items rows of the open View Details drawer as lists of cell texts (Details, Qty, Price, Discount, Total, Cost, Profit)."""
        rows = self.page.locator("[role=dialog]:visible tbody tr.ant-table-row")
        return [[c.strip() for c in rows.nth(i).locator("td").all_inner_texts()] for i in range(rows.count())]

    def open_details(self, index: int = 0) -> "SaleRecordPage":
        self.open_row_action(index, "View Details")
        self.page.locator("[role=dialog]:visible tbody tr.ant-table-row").first.wait_for(state="visible", timeout=30_000)
        self.page.wait_for_timeout(1_500)
        return self

    def action_enabled(self, index: int, action: str) -> bool:
        """Whether a row-menu item is clickable (the menu is closed again afterwards)."""
        self.page.locator(ROWS).nth(index).locator(".ant-dropdown-trigger").last.click()
        item = self.page.locator(".ant-dropdown:not(.ant-dropdown-hidden) li").filter(has_text=action).first
        item.wait_for(state="visible", timeout=10_000)
        enabled = item.get_attribute("aria-disabled") != "true"
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        return enabled

    def cancel_row(self, index: int = 0) -> str:
        """Row Actions > Cancel Sale > Yes, cancel it (single click); the toast text."""
        self.open_row_action(index, "Cancel Sale")
        self.page.get_by_role("button", name="Yes, cancel it").click(timeout=15_000)
        for _ in range(30):
            self.page.wait_for_timeout(500)
            msgs = self.toast_messages()
            if msgs:
                return " | ".join(msgs)
        return ""

    def edit_first_line_qty(self, index: int, qty) -> str:
        """Row Actions > Edit Sale; change the quantity of the first cart line, Update Sale (settling an excess/shortfall with the
        walk-in option); returns the toast text."""
        self.open_row_action(index, "Edit Sale")
        self.page.get_by_text("Add to Cart").first.wait_for(timeout=90_000)
        self.page.wait_for_timeout(6_000)
        self.page.locator("main tbody tr").filter(has=self.page.locator(".ant-flex.ant-flex-justify-center")).first \
            .locator(".ant-flex.ant-flex-justify-center > div:nth-child(1)").click()
        self.page.wait_for_timeout(1_500)
        self.page.locator("#qty").fill(str(qty))
        self.page.get_by_role("button", name="Save Changes").click()
        self.page.wait_for_timeout(2_000)
        self.page.get_by_text("Go to Sale Checkout").first.click()
        self.page.get_by_role("button", name="Update Sale").wait_for(timeout=60_000)
        self.page.wait_for_timeout(2_000)
        self.page.get_by_role("button", name="Update Sale").click()
        self.page.wait_for_timeout(3_000)
        for label in ("Profit & Sale", "Less & Sale"):
            option = self.page.get_by_text(label)
            if option.count() and option.first.is_visible():
                option.first.click()
                break
        for _ in range(40):
            self.page.wait_for_timeout(500)
            msgs = self.toast_messages()
            if msgs:
                return " | ".join(msgs)
        return ""

    def confirm_cancel_double_click(self) -> int:
        """After Row Actions > Cancel Sale: double-click 'Yes, cancel it'; how many cancel requests were sent within 8 s."""
        sent: list[str] = []
        handler = lambda r: sent.append(r.url) if r.method in ("POST", "PUT", "PATCH", "DELETE") and "cancel" in r.url.lower() else None  # noqa: E731
        self.page.on("request", handler)
        try:
            self.page.get_by_role("button", name="Yes, cancel it").dblclick(timeout=15_000)
            self.page.wait_for_timeout(8_000)
        finally:
            self.page.remove_listener("request", handler)
        return len(sent)

    def total_sales_tile(self) -> int:
        m = re.search(r"Total Sales\s*\((\d+)\)", self.page.locator("main").inner_text())
        assert m, "Total Sales tile not found"
        return int(m.group(1))
