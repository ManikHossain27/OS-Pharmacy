"""Inventory Return: the Return form + Return Cart + Return Checkout (route /inventory-return) and the Inventory
Return Record (route /inventory-return-record).

The form is reached from the sidebar (empty cart) or from an Inventory Record row menu (route
``/inventory-return?inventoryId=<id>``, which pre-loads that inventory's lines, in pieces, into the cart).
"Go to Return Checkout" opens the checkout panel on the same page (Supplier, Demurrage, Invoice number, Note,
Complete Inventory Return).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import allure
from playwright.sync_api import Locator, Page

from pages.base_page import BasePage
from pages.inventory_record_page import InventoryRecordPage
from utils.helpers import money

RETURN_URL = re.compile(r"/inventory-return\?inventoryId=(\d+)")
OPTION = ".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option"
SUCCESS_TOAST = "Inventory return has been submitted successfully"


def _num(text: str) -> float:
    m = re.search(r"-?[\d,]+(?:\.\d+)?", text or "")
    return float(m.group().replace(",", "")) if m else float("nan")


@dataclass
class CartLine:
    product: str
    qty: float            # as typed (pieces or boxes)
    unit: str             # "pc" | "box"
    pieces: float         # total pieces (qty x pieces per box when returned by box)
    batch: str
    price_per_unit: float
    unit_label: str       # "pc" | "box"
    price: float          # the line's Price column


class InventoryReturnPage(BasePage):
    ROUTE = "/inventory-return"

    def __init__(self, page: Page):
        super().__init__(page)
        self.rows = page.locator("tbody tr.ant-table-row")
        self.add_btn = page.get_by_role("button", name="Add to Return Cart")
        self.checkout_btn = page.get_by_role("button", name="Go to Return Checkout")
        self.complete_btn = page.get_by_role("button", name="Complete Inventory Return")
        self.qty_input = page.locator("#returnQty")
        self._per_box: dict[str, float] = {}   # pieces per box by batch, learnt from the Batch dropdown (the cart shows boxes only)

    # ------------------------------------------------------------------ opening
    @allure.step("Open Inventory Return")
    def open(self, route: str | None = None) -> "InventoryReturnPage":
        self.page.goto(self.ROUTE)
        return self.wait_loaded()

    def wait_loaded(self) -> "InventoryReturnPage":
        self.page.locator("#productId").wait_for(state="visible", timeout=90_000)
        self.page.wait_for_timeout(800)
        return self

    @allure.step("Open Return Inventory for {inventory_id}")
    def open_for(self, record: InventoryRecordPage, inventory_id: str) -> "InventoryReturnPage":
        record.choose_row_action(record.row_by_inventory_id(inventory_id), "Return Inventory")
        self.page.wait_for_url(RETURN_URL, timeout=30_000)
        self.page.get_by_text("Total Return from Supplier").wait_for(state="visible", timeout=60_000)
        self.page.wait_for_timeout(1000)
        return self

    # ------------------------------------------------------------------ the form
    def _options(self) -> list[str]:
        self.page.wait_for_timeout(700)
        return [t.strip() for t in self.page.locator(OPTION).all_inner_texts()]

    def _pick(self, field_id: str, text: str, *, type_text: str | None = None, exact: bool = False) -> None:
        self.page.locator(f"#{field_id}").click()
        if type_text:
            self.page.keyboard.type(type_text)
        match = re.compile(rf"^\s*{re.escape(text)}\s*$", re.I) if exact else text
        option = self.page.locator(OPTION).filter(has_text=match).first
        option.wait_for(state="visible", timeout=30_000)
        option.click()
        self.page.wait_for_timeout(500)

    def select_company(self, name: str) -> None:
        self._pick("companyId", name, type_text=name)

    def company_options(self) -> list[str]:
        self.page.locator("#companyId").click()
        opts = self._options()
        self.page.keyboard.press("Escape")
        return opts

    def search_products(self, term: str) -> list[str]:
        """The Product dropdown's options after typing ``term``."""
        self.page.locator("#productId").click()
        self.page.keyboard.type(term)
        opts = self._options()
        self.page.keyboard.press("Escape")
        return opts

    def select_product(self, term: str) -> None:
        self._pick("productId", term, type_text=term)

    def selected_product(self) -> str:
        return self.page.locator("#productId").locator("xpath=ancestor::div[contains(@class,'ant-select')][1]").inner_text().strip()

    def batch_options(self) -> list[dict]:
        """[{batch, pcs, boxes}] the Batch No dropdown offers for the selected product."""
        self.page.locator("#batchNo").click()
        out = []
        for t in self._options():
            m = re.match(r"(.+?)\s*\n?\s*PC:\s*([\d.,]+)\s*\n?\s*Box:\s*([\d.,]+)", t)
            out.append({"batch": m.group(1).strip(), "pcs": _num(m.group(2)), "boxes": _num(m.group(3))} if m else {"batch": t})
        self.page.keyboard.press("Escape")
        return out

    def select_batch(self, batch: str) -> None:
        self._pick("batchNo", batch)

    def selected_batch_text(self) -> str:
        return self.page.locator("#batchNo").locator("xpath=ancestor::div[contains(@class,'ant-select')][1]").inner_text().strip()

    def available(self) -> float:
        """Available pieces of the selected batch - the number in 'BATCH (20)'."""
        m = re.search(r"\(([\d.,]+)\)\s*$", self.selected_batch_text())
        return _num(m.group(1)) if m else float("nan")

    def unit_options(self) -> list[str]:
        self.page.locator("#returnQtyUnit").click()
        opts = self._options()
        self.page.keyboard.press("Escape")
        return opts

    def set_unit(self, unit: str) -> None:
        self._pick("returnQtyUnit", unit, exact=True)

    def unit(self) -> str:
        return self.page.locator("#returnQtyUnit").locator("xpath=ancestor::div[contains(@class,'ant-select')][1]").inner_text().strip()

    def set_qty(self, value) -> None:
        self.qty_input.click()
        self.qty_input.fill("" if value is None else str(value))

    def qty_error(self) -> str:
        err = self.page.locator(".ant-form-item-explain-error")
        return err.first.inner_text().strip() if err.count() else ""

    def add_enabled(self) -> bool:
        return self.add_btn.is_enabled()

    @allure.step("Add {qty} {unit} of {product} / {batch} to the Return Cart")
    def add_line(self, product: str, batch: str, qty, unit: str = "pc") -> None:
        self.select_product(product)
        self.select_batch(batch)
        if unit.lower() == "box" and batch not in self._per_box:
            mine = next((b for b in self.batch_options() if b.get("batch") == batch and b.get("boxes")), None)
            if mine:
                self._per_box[batch] = round(mine["pcs"] / mine["boxes"])
        if unit.lower() != self.unit().lower():
            self.set_unit(unit)
        self.set_qty(qty)
        self.add_btn.click()
        self.page.wait_for_timeout(700)

    def add_current(self) -> None:
        self.add_btn.click()
        self.page.wait_for_timeout(700)

    # ------------------------------------------------------------------ cart
    def cart_lines(self) -> list[CartLine]:
        out = []
        for i in range(self.rows.count()):
            cells = [c.strip() for c in self.rows.nth(i).locator("td").all_inner_texts()]
            if len(cells) < 5:
                continue
            product = cells[0].splitlines()[0].strip()
            q = [x.strip() for x in cells[1].splitlines() if x.strip()]
            unit = next((x.lower() for x in q if x.lower() in ("pc", "box", "pcs", "boxes")), "pc")
            unit = "box" if unit.startswith("box") else "pc"
            qty = _num(q[0])
            paren = re.search(r"\(?([\d.,]+)\s*pc", " ".join(q[1:]), re.I)
            batch = cells[2].splitlines()[0].strip()
            pieces = _num(paren.group(1)) if paren and unit == "box" else qty * (self._per_box.get(batch, 1) if unit == "box" else 1)
            price_cell = [x.strip() for x in cells[3].splitlines() if x.strip()]
            out.append(CartLine(product, qty, unit, pieces, batch,
                                _num(price_cell[0]), price_cell[-1].lower().replace("per", "").strip() or "pc",
                                _num(cells[4])))
        return out

    def cart_rows(self) -> list[dict]:
        """Return Cart lines as {batch, qty (pieces), price (line total)}."""
        return [{"batch": l.batch, "qty": int(l.pieces), "price": l.price} for l in self.cart_lines()]

    def cart_total(self) -> float:
        text = self.page.get_by_text("Total Return from Supplier").first.locator("xpath=..").inner_text()
        return money(text.split("Supplier", 1)[-1].split("Go to")[0])

    def empty_cart_visible(self) -> bool:
        return self.page.get_by_text("No Items to Return").count() > 0

    def _row_action(self, index: int, which: int) -> Locator:
        return self.rows.nth(index).locator("td").last.locator("svg, button").nth(which)

    @allure.step("Edit Return Cart row {index}")
    def edit_row(self, index: int) -> None:
        self._row_action(index, 0).click()
        self.page.wait_for_timeout(700)

    @allure.step("Delete Return Cart row {index}")
    def delete_row(self, index: int) -> None:
        self._row_action(index, 1).click()
        confirm = self.page.get_by_role("button", name=re.compile(r"^(Yes|OK|Delete|Remove)", re.I))
        if confirm.count():
            confirm.first.click()
        self.page.wait_for_timeout(700)

    def update_btn_visible(self) -> bool:
        return self.page.get_by_role("button", name="Update Cart").count() > 0

    def update_cart(self) -> None:
        self.page.get_by_role("button", name="Update Cart").click()
        self.page.wait_for_timeout(700)

    # ------------------------------------------------------------------ checkout
    @allure.step("Go to Return Checkout")
    def go_to_checkout(self) -> "InventoryReturnPage":
        self.checkout_btn.click()
        self.complete_btn.wait_for(state="visible", timeout=30_000)
        return self

    def checkout_enabled(self) -> bool:
        return self.checkout_btn.is_enabled()

    def _selects(self) -> Locator:
        return self.page.locator(".ant-select:visible")

    def _supplier_select(self) -> Locator:
        return self._selects().nth(4)

    def supplier_preselected(self) -> bool:
        return self.page.locator(".ant-select", has_text="Select supplier").count() == 0

    def supplier_options(self) -> list[str]:
        self._supplier_select().click()
        opts = [o.splitlines()[0].strip() for o in self._options()]
        self.page.keyboard.press("Escape")
        return opts

    def select_supplier(self, name: str) -> None:
        self._supplier_select().click()
        self.page.locator(OPTION).filter(has_text=name).first.click()
        self.page.wait_for_timeout(700)

    def selected_supplier(self) -> str:
        return self._supplier_select().inner_text().splitlines()[0].strip()

    def set_demurrage(self, value, unit: str = "%") -> None:
        if unit != self._selects().nth(5).inner_text().strip():
            self._selects().nth(5).click()
            self.page.locator(OPTION).filter(has_text=re.compile(rf"^{re.escape(unit)}$")).first.click()
        box = self.page.get_by_placeholder("Enter demurrage amount")
        box.click()
        box.fill("" if value is None else str(value))
        self.page.wait_for_timeout(700)

    def demurrage_value(self) -> str:
        return self.page.get_by_placeholder("Enter demurrage amount").input_value()

    def demurrage_unit(self) -> str:
        return self._selects().nth(5).inner_text().strip()

    def set_invoice(self, text: str) -> None:
        self.page.get_by_placeholder("Enter invoice number here").fill(text)

    def set_note(self, text: str) -> None:
        self.page.get_by_placeholder("Type a note here...").fill(text)

    def _panel_text(self) -> str:
        text = self.page.locator("body").inner_text()
        i = text.rfind("Return Checkout\n")
        return text[i:] if i >= 0 else ""

    def summary(self) -> dict:
        """The checkout panel's figures. Balances are signed (+ Due, - Advance)."""
        t = self._panel_text()
        lines = [l.strip() for l in t.splitlines() if l.strip()]

        def after(label: str) -> float:
            for i, l in enumerate(lines):
                if l.startswith(label) and i + 1 < len(lines):
                    return _num(lines[i + 1])
            return float("nan")

        def balance(label: str) -> float:
            for i, l in enumerate(lines):
                if l.startswith(label) and i + 1 < len(lines):
                    v = _num(lines[i + 1])
                    return -v if "(Adv" in l else v
            return float("nan")
        # the summary row is the LAST "Demurrage Amount" line ("Demurrage Amount (10%)" in %, plain in Tk); the first is the input
        dem_row = max((i for i, l in enumerate(lines) if l.startswith("Demurrage Amount")), default=-1)
        dem = lines[dem_row] if dem_row >= 0 else ""
        return {
            "previous_balance": balance("Previous Balance"),
            "new_balance": balance("New Balance"),
            "total_items": after("Total Items"),
            "total_price": after("Total Return Price"),
            "demurrage": _num(lines[dem_row + 1]) if dem_row >= 0 and dem_row + 1 < len(lines) else 0.0,
            "demurrage_label": dem,
            "round_off": after("Round Off") if any(l.startswith("Round Off") for l in lines) else 0.0,
            "final_price": after("Final Price (Return from Supplier)"),
        }

    def final_price(self) -> float:
        return self.summary()["final_price"]

    def complete_enabled(self) -> bool:
        return self.complete_btn.is_enabled()

    @allure.step("Complete Inventory Return, capturing the response")
    def complete(self) -> tuple[int | None, str]:
        def _is_return(resp) -> bool:
            return resp.request.method in ("POST", "PUT") and "return" in resp.url.lower()
        try:
            with self.page.expect_response(_is_return, timeout=60_000) as info:
                self.complete_btn.click()
            resp = info.value
            status, body = resp.status, resp.text()
        except Exception:
            status, body = None, ""
        self.page.wait_for_timeout(1500)
        return status, body

    def toast_text(self) -> str:
        return " | ".join(self.toast_messages())


class InventoryReturnRecordPage(BasePage):
    ROUTE = "/inventory-return-record"

    def __init__(self, page: Page):
        super().__init__(page)
        self.rows = page.locator("tbody tr.ant-table-row")

    @allure.step("Open Inventory Return Record")
    def open(self, route: str | None = None) -> "InventoryReturnRecordPage":
        self.page.goto(self.ROUTE)
        return self.wait_loaded()

    def wait_loaded(self) -> "InventoryReturnRecordPage":
        self.page.get_by_text("Total Returns").first.wait_for(state="visible", timeout=90_000)
        self.page.wait_for_timeout(2500)
        return self

    def summary(self) -> dict:
        t = self.page.locator("body").inner_text()
        m1 = re.search(r"Total Returns\s*\((\d+)\)\s*Tk\s*([\d,.\-]+)", t)
        m2 = re.search(r"Total Demurrage\s*\((\d+)\)\s*Tk\s*([\d,.\-]+)", t)
        g = lambda m, i: _num(m.group(i)) if m else float("nan")
        return {"returns_count": g(m1, 1), "returns_total": g(m1, 2), "demurrage_count": g(m2, 1), "demurrage_total": g(m2, 2)}

    def row_count(self) -> int:
        return self.rows.count()

    def row_values(self, row: Locator) -> dict:
        cells = [c.strip() for c in row.locator("td").all_inner_texts()]
        idl = cells[0].splitlines()
        sup = cells[1].splitlines()
        return {"id": idl[0].strip(), "date": idl[1].strip() if len(idl) > 1 else "",
                "supplier": sup[0].strip(), "phone": sup[1].strip() if len(sup) > 1 else "",
                "items": cells[2], "price": _num(cells[3]), "demurrage": cells[4], "status": cells[5],
                "updated_by": cells[6]}

    def all_rows(self) -> list[dict]:
        return [self.row_values(self.rows.nth(i)) for i in range(self.rows.count())]

    def first_row(self) -> dict:
        self.rows.first.wait_for(state="visible", timeout=60_000)
        return self.row_values(self.rows.first)

    def row_by_id(self, return_id: str) -> Locator:
        return self.rows.filter(has_text=return_id).first

    def _menu_trigger(self, row: Locator) -> Locator:
        return row.locator("td").last.locator(".custom-drop-down-btn, button").last

    def menu_items(self, row: Locator) -> list[str]:
        self._menu_trigger(row).click()
        self.page.wait_for_timeout(500)
        items = [t.strip() for t in self.page.locator(".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-item").all_inner_texts()]
        return items

    def choose_action(self, row: Locator, label: str) -> None:
        self._menu_trigger(row).click()
        self.page.wait_for_timeout(500)
        self.page.locator(".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-item", has_text=label).first.click()
        self.page.wait_for_timeout(1500)

    def open_details(self, row: Locator) -> str:
        """Open Return Details and return the dialog text (from 'Inventory Return Details')."""
        self.choose_action(row, "View Details")
        self.page.get_by_text("Inventory Return Details").first.wait_for(state="visible", timeout=30_000)
        self.page.wait_for_timeout(1500)
        text = self.page.locator("body").inner_text()
        return text[text.rfind("Inventory Return Details"):]

    def close_details(self) -> None:
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    @allure.step("Cancel the return {return_id}")
    def cancel_return(self, return_id: str) -> None:
        self.choose_action(self.row_by_id(return_id), "Cancel Return")
        btn = self.page.get_by_role("button", name=re.compile(r"Yes, cancel", re.I))
        btn.first.wait_for(state="attached", timeout=15_000)
        btn.first.dispatch_event("click")      # the popover renders off-screen at 1920px (BUG-INV-026)
        self.page.wait_for_timeout(3000)

    # ---- filters
    def search_supplier(self, name: str) -> None:
        """Pick a supplier in the 'Search by supplier name' select."""
        self.page.locator(".ant-select", has_text="Search by supplier name").first.click()
        self.page.locator(OPTION).filter(has_text=name).first.click()
        self.page.wait_for_timeout(2500)

    def search_text(self, text: str) -> None:
        """The 'Search by return id or product' box."""
        box = self.page.get_by_placeholder("Search by return id or product...")
        box.fill(text)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2500)

    def set_date_range(self, start: str, end: str) -> None:
        """Type the Start / End date (YYYY-MM-DD) into the range picker."""
        self.page.get_by_placeholder("Start date").click()
        self.page.keyboard.type(start)
        self.page.keyboard.press("Enter")
        self.page.keyboard.type(end)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2500)

    def showing(self) -> tuple[int, int, int]:
        """('Showing a-b of n') as (a, b, n); zeros when absent."""
        m = re.search(r"Showing\s+(\d+)-(\d+)\s+of\s+(\d+)", re.sub(r"\s+", " ", self.page.locator("body").inner_text()))
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    def goto_page(self, n: int) -> None:
        self.page.locator(".ant-pagination-item", has_text=re.compile(rf"^{n}$")).first.click()
        self.page.wait_for_timeout(2500)

    def next_page(self) -> None:
        self.page.locator(".ant-pagination-next").click()
        self.page.wait_for_timeout(2500)

    def previous_enabled(self) -> bool:
        return self.page.locator(".ant-pagination-prev").get_attribute("aria-disabled") != "true"

    def set_page_size(self, n: int) -> None:
        self.page.locator(".ant-select", has_text=re.compile(r"^\d+$")).last.click()
        self.page.locator(OPTION).filter(has_text=re.compile(rf"^{n}$")).first.click()
        self.page.wait_for_timeout(2500)

    def choose_status(self, option: str) -> None:
        self.page.locator(".ant-select").nth(1).click()   # the status select keeps its slot once a status is chosen
        self.page.locator(OPTION).filter(has_text=option).first.click()
        self.page.wait_for_timeout(2500)

    def reset_filters(self) -> None:
        self.page.get_by_role("button", name="Reset Filters").click()
        self.page.wait_for_timeout(2500)
