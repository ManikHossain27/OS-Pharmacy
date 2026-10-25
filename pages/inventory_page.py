"""Inventory (route: /inventory, /inventory/tp-vat, /inventory/opening-stock).

The "Add Items to Cart" panel is an inline side panel (not an ``.ant-drawer``
like Add New Product), always visible unless the user closes it. Field ids are
stable and shared across modes except for the purchase-price fields:

  Default:       btpVatPerBox / totalItemPrice
  TP/VAT:        tpPerBox / vatPerBox
  Opening Stock: btpVatPerBox / totalItemPrice / openingStockPercent

See ``utils.constants.INVENTORY_FIELDS_BY_MODE``.
"""
from __future__ import annotations

import re
from typing import Any

import allure
from playwright.sync_api import Locator, Page, expect

from components.antd_select import AntdSelect
from components.data_table import DataTable
from pages.base_page import BasePage
from utils.constants import (
    INVENTORY_FIELDS_BY_MODE,
    INVENTORY_MODE_LABELS,
    INVENTORY_MODE_ROUTES,
    ROUTES,
)


class InventoryPage(BasePage):
    route = ROUTES["inventory"]

    def __init__(self, page: Page):
        super().__init__(page)
        self.company_select = AntdSelect(page, "companyId", clicker=self.click)
        self.product_select = AntdSelect(page, "productId", clicker=self.click)
        self.storage_type_select = AntdSelect(page, "storageType", clicker=self.click)

        self.cart = DataTable(page)  # header+body <table>s live in <main>; Hold List dialog is portaled outside it
        self.hold_list_btn = page.get_by_role("button", name=re.compile(r"^\d+\s*Hold List$"))
        self.bulk_import_btn = page.get_by_role("button", name="Bulk Import")
        self.add_new_product_btn = page.get_by_role("button", name="Add New Product")
        self.hold_current_btn = page.get_by_role("button", name="Hold Current Inventory")
        self.go_to_checkout_btn = page.get_by_role("button", name="Go to Inventory Checkout")
        self.close_panel_btn = page.get_by_role("button", name="Close", exact=True)   # exact: a substring match also hits the sidebar "Cash Closer" link

        self.cart_total_root = page.locator(".inventory-cart-total")

    # ------------------------------------------------------------------ nav
    def open(self, mode: str = "Default") -> "InventoryPage":
        slug = INVENTORY_MODE_ROUTES[mode]
        self.page.goto(self.base_url + slug, wait_until="domcontentloaded")
        self.wait_for_app_ready()
        return self.wait_loaded()

    def _form_clean(self) -> bool:
        snap = self.form_snapshot()
        return (not snap.get("product") and not snap.get("batch_no") and snap.get("free_qty", "") in ("", "0")
                and snap.get("box_qty", "") in ("", "0"))

    def _clear_form(self) -> None:
        """Empty the create form in place (no navigation, no mode switching)."""
        try:
            self.product_select.clear()
        except Exception:
            pass
        for key in ("box_qty", "total_qty", "free_qty", "price_per_box", "total_price", "retail_price",
                    "wholesale_price", "min_qty", "rack_no", "batch_no", "barcode_value", "special_discount"):
            try:
                loc = self.field(key)
                if loc.count():
                    loc.fill("")
            except Exception:
                pass

    def soft_reset(self) -> bool:
        """Cheap client-side reset to a clean Default form WITHOUT reloading the SPA
        (a cold reload of the staging dev build costs ~60 s) and without clicking around:
        a form that is already clean (the usual case - the form empties itself after Add
        Items to Cart) is left untouched; a dirty one is cleared field by field. Mode
        switching is only a last resort. Returns False when the page is not on the Default
        route or the form could not be cleaned, so the caller falls back to a full ``open()``."""
        try:
            if not self.page.url.rstrip("/").endswith("/" + INVENTORY_MODE_ROUTES["Default"]):
                return False
            if self.current_mode() != "Default" or self.is_edit_mode():
                return False
            self.open_add_items_panel()
            if self._form_clean():
                return True
            self._clear_form()
            return self._form_clean()
        except Exception:
            return False

    def is_loaded(self) -> bool:
        return self.page.get_by_role("radio", name="Inventory").count() > 0

    def wait_loaded(self) -> "InventoryPage":
        expect(self.page.get_by_role("combobox", name=re.compile(r"Product"))).to_be_visible(timeout=60_000)
        return self

    # ------------------------------------------------------------------ mode
    mode_override: str | None = None   # the edit screens have no mode radios; the edit page sets the record's mode

    def current_mode(self) -> str:
        if self.mode_override:
            return self.mode_override
        for m in INVENTORY_MODE_LABELS:
            radio = self.page.get_by_role("radio", name=m, exact=True)
            if radio.count() and radio.is_checked():
                return m
        return "Default"

    @allure.step("Switch Inventory Mode to {mode}")
    def switch_mode(self, mode: str) -> "InventoryPage":
        assert mode in INVENTORY_MODE_LABELS, f"unknown inventory mode {mode!r}"
        if self.current_mode() == mode:
            return self
        label = self.page.locator("label").filter(has=self.page.get_by_role("radio", name=mode, exact=True))
        self.click(label, expect_effect=lambda: self.current_mode() == mode,
                   description=f"Inventory Mode -> {mode}")
        try:      # the panel opens by default in a mode unless the user closed it there (spec 3) - don't require it
            expect(self.page.get_by_role("combobox", name=re.compile(r"Product"))).to_be_visible(timeout=5_000)
        except AssertionError:
            pass
        return self

    def panel_open(self) -> bool:
        return self.page.get_by_role("combobox", name=re.compile(r"Product")).count() > 0

    def open_add_items_panel(self) -> "InventoryPage":
        """The panel auto-opens on mode change; reopen it if the user closed it."""
        if self.panel_open():
            return self
        header = self.page.get_by_text("Add Items to Cart", exact=True)
        self.click(header, expect_effect=self.panel_open, description="reopen Add Items to Cart")
        return self

    def close_add_items_panel(self) -> None:
        self.click(self.close_panel_btn, expect_effect=lambda: not self.panel_open(),
                   description="close Add Items to Cart")

    # ------------------------------------------------------------------ fields
    def _field_map(self) -> dict[str, str]:
        return INVENTORY_FIELDS_BY_MODE[self.current_mode()]

    def field(self, key: str) -> Locator:
        fmap = self._field_map()
        assert key in fmap, f"{key!r} not a field in {self.current_mode()} mode ({list(fmap)})"
        return self.page.locator(f"#{fmap[key]}")

    def set_value(self, key: str, value: Any) -> None:
        loc = self.field(key)
        loc.fill("")
        loc.fill(str(value))

    def type_value(self, key: str, text: str) -> str:
        """Type ``text`` with the REAL keyboard (select-all, delete, then key presses) and return what the
        field holds afterwards. ``set_value`` uses ``fill()``, which writes the value straight into the input
        and bypasses the field's own key filtering - use this whenever the typed characters themselves matter."""
        loc = self.field(key)
        loc.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Backspace")
        if text:
            loc.press_sequentially(text, delay=50)
        loc.blur()
        self.page.wait_for_timeout(300)
        return loc.input_value()

    def value_of(self, key: str) -> str:
        return self.field(key).input_value()

    def select_product(self, name: str, *, exact: bool = False) -> "InventoryPage":
        """``exact=True`` means "the product whose NAME is exactly ``name``". The control shows
        ``NAME - generic - strength - type`` once selected, and the dropdown search is a
        fuzzy contains-match, so select by typed name and then VERIFY the chosen name."""
        self.product_select.select(name, exact=False)
        if exact:
            shown = self.product_select.selected_text().casefold()
            assert shown == name.casefold() or shown.startswith(name.casefold() + " - "),                 f"selected product {shown!r} is not {name!r}"
        return self

    def select_company(self, name: str, *, exact: bool = False) -> "InventoryPage":
        self.company_select.select(name, exact=exact)
        return self

    def select_storage_type(self, value: str) -> "InventoryPage":
        self.storage_type_select.select(value)
        return self

    # ------------------------------------------------------------------ expiry date
    @allure.step("Set Expiry Date to {day}/{month_abbr}/{year}")
    def set_expiry_date(self, day: int, month_abbr: str, year: int) -> None:
        """Navigate the AntD calendar - typing a raw date string into the field
        does NOT register (the value reverts to empty on blur); the picker must
        actually be clicked through."""
        field = self.field("expiry_date")
        self.click(field, expect_effect=lambda: self.page.get_by_role("button", name="Choose a year").is_visible(),
                   description="open Expiry Date picker")
        self.click(self.page.get_by_role("button", name="Choose a year"), description="open year picker")
        # the year panel opens on the current decade (2020-2029): step forward until the year shows
        for _ in range(8):
            if self.page.get_by_role("cell", name=str(year), exact=True).count():
                break
            self.click(self.page.locator(".ant-picker-header-super-next-btn").last, description="next decade")
        self.click(self.page.get_by_role("cell", name=str(year), exact=True), description=f"pick year {year}")
        self.click(self.page.get_by_role("cell", name=month_abbr, exact=True), description=f"pick month {month_abbr}")
        day_cell = self.page.locator("td.ant-picker-cell-in-view").filter(
            has_text=re.compile(rf"^{day}$")
        )
        self.click(day_cell.first, description=f"pick day {day}")

    def expiry_date_text(self) -> str:
        return self.field("expiry_date").input_value()

    def expiry_past_dates_disabled(self) -> bool | None:
        """Open the Expiry Date calendar (defaults to the current month, which
        always contains at least one date before today unless today is the
        1st) and check whether every visible date earlier than today carries
        AntD's `ant-picker-cell-disabled` class. Past dates are INTENTIONALLY
        selectable (confirmed 2026-10-08, BUG-INV-014 closed). Originally written against 'Invalid
        expiry - Should not be accepted'. Returns None if no past-date cell
        is in the current view (caller should treat that as inconclusive)."""
        field = self.field("expiry_date")
        self.click(field, expect_effect=lambda: self.page.get_by_role("button", name="Choose a year").is_visible(),
                   description="open Expiry Date picker")
        return self.page.evaluate(
            """() => {
                const today = new Date(); today.setHours(0, 0, 0, 0);
                const cells = Array.from(document.querySelectorAll('.ant-picker-cell'));
                const past = cells.filter(c => {
                    const t = c.getAttribute('title');
                    if (!t) return false;
                    return new Date(t + 'T00:00:00') < today;
                });
                if (past.length === 0) return null;
                return past.every(c => c.classList.contains('ant-picker-cell-disabled'));
            }"""
        )

    # ------------------------------------------------------------------ submit
    def submit_button(self) -> Locator:
        return self.page.get_by_role("button", name=re.compile(r"^(Add Items to Cart|Save Changes)$"))

    def is_edit_mode(self) -> bool:
        return self.page.get_by_text("Edit Cart Item", exact=True).count() > 0

    @allure.step("Submit cart item")
    def submit_cart_item(self) -> None:
        before = self.total_items()
        editing = self.is_edit_mode()
        self.click(self.submit_button(), description="Add/Save cart item")
        if editing:
            self._poll(lambda: not self.is_edit_mode(), timeout=6_000)
        else:
            self._poll(lambda: self.total_items() > before, timeout=6_000)

    # ------------------------------------------------------------------ high-level add
    @allure.step("Add item to cart")
    def add_item_to_cart(
        self,
        *,
        product: str,
        box_qty: Any,
        free_qty: Any = None,
        batch_no: str | None = None,
        expiry: tuple[int, str, int] | None = None,
        retail_price: Any = None,
        wholesale_price: Any = None,
        min_qty: Any = None,
        rack_no: Any = None,
        barcode_value: str | None = None,
        **mode_fields: Any,
    ) -> None:
        """``mode_fields`` are mode-specific purchase-price keys, e.g.
        ``price_per_box=`` (Default/Opening Stock) or ``tp_per_box=``,
        ``vat_per_box=`` (TP/VAT)."""
        self.select_product(product)
        self.set_value("box_qty", box_qty)
        if free_qty is not None:
            self.set_value("free_qty", free_qty)
        for key, value in mode_fields.items():
            self.set_value(key, value)
        if retail_price is not None:
            self.set_value("retail_price", retail_price)
        if wholesale_price is not None:
            self.set_value("wholesale_price", wholesale_price)
        if min_qty is not None:
            self.set_value("min_qty", min_qty)
        if rack_no is not None:
            self.set_value("rack_no", rack_no)
        if batch_no is not None:
            self.set_value("batch_no", batch_no)
        if barcode_value is not None:
            self.set_value("barcode_value", barcode_value)
        if expiry is not None:
            self.set_expiry_date(*expiry)
        self.submit_cart_item()

    # ------------------------------------------------------------------ form snapshot / spec-driven add
    def form_snapshot(self) -> dict[str, str]:
        """Raw text of every input of the current mode's form, keyed by logical field name."""
        snap: dict[str, str] = {}
        for key in self._field_map():
            loc = self.field(key)
            if loc.count():
                snap[key] = loc.input_value()
        return snap

    def form_number(self, key: str) -> float:
        raw = self.value_of(key).replace(",", "").strip()
        return float(raw) if raw else 0.0

    def field_is_enabled(self, key: str) -> bool:
        return self.field(key).is_enabled()

    @allure.step("Add line from spec")
    def add_line(self, spec, batch: str):
        """Fill the create form from a ``LineSpec`` and submit it; return the
        oracle ``Line`` built from the values the FORM actually held (product
        defaults the user did not override are read back, never assumed)."""
        from utils.inventory_calc import Line
        product = self.resolve_product(spec.product)
        self.select_product(product, exact=True)
        if spec.btp_vat_per_box is not None:
            self.set_value("price_per_box", spec.btp_vat_per_box)
        self.set_value("box_qty", spec.box_qty)
        self.field("box_qty").blur()
        if spec.free_qty:
            self.set_value("free_qty", spec.free_qty)
        if spec.retail is not None:
            self.set_value("retail_price", spec.retail)
        if spec.wholesale is not None:
            self.set_value("wholesale_price", spec.wholesale)
        if spec.min_qty is not None:
            self.set_value("min_qty", spec.min_qty)
        if spec.rack is not None:
            self.set_value("rack_no", spec.rack)
        self.set_value("batch_no", spec.batch or batch)
        if spec.barcode:
            self.set_value("barcode_value", spec.barcode)
        if spec.expiry:
            self.set_expiry_date(*spec.expiry)
        if spec.special:
            self.type_value("special_discount", str(spec.special))
        line = Line(name=product, box_qty=self.form_number("box_qty"), qty_per_box=self.form_number("qty_per_box"),
                    btp_vat_per_box=self.form_number("price_per_box"), free_qty=self.form_number("free_qty"),
                    retail_per_box=self.form_number("retail_price"),
                    wholesale_per_box=self.form_number("wholesale_price"))
        self.submit_cart_item()
        return line

    @allure.step("Add TP/VAT line from spec")
    def add_tpvat_line(self, spec, batch: str):
        """TP/VAT counterpart of ``add_line``: fills TP/Box (VAT/Box is auto-filled at the system rate unless
        the spec gives one - typed AFTER TP, because editing TP re-derives VAT) and returns the oracle
        ``TpVatLine`` built from what the FORM held."""
        from utils.tpvat_calc import TpVatLine
        product = self.resolve_product(spec.product)
        self.select_product(product, exact=True)
        if spec.tp_per_box is not None:
            self.set_value("tp_per_box", spec.tp_per_box)
            self.field("tp_per_box").blur()
            self.page.wait_for_timeout(250)
        if spec.vat_per_box is not None:
            self.set_value("vat_per_box", spec.vat_per_box)
            self.field("vat_per_box").blur()
        self.set_value("box_qty", spec.box_qty)
        self.field("box_qty").blur()
        if spec.free_qty:
            self.set_value("free_qty", spec.free_qty)
        if spec.retail is not None:
            self.set_value("retail_price", spec.retail)
        if spec.wholesale is not None:
            self.set_value("wholesale_price", spec.wholesale)
        if spec.min_qty is not None:
            self.set_value("min_qty", spec.min_qty)
        if spec.rack is not None:
            self.set_value("rack_no", spec.rack)
        self.set_value("batch_no", spec.batch or batch)
        if spec.barcode:
            self.set_value("barcode_value", spec.barcode)
        if spec.expiry:
            self.set_expiry_date(*spec.expiry)
        if spec.special:
            self.type_value("special_discount", str(spec.special))
        line = TpVatLine(name=product, box_qty=self.form_number("box_qty"), qty_per_box=self.form_number("qty_per_box"),
                         tp_per_box=self.form_number("tp_per_box"), vat_per_box=self.form_number("vat_per_box"),
                         free_qty=self.form_number("free_qty"), retail_per_box=self.form_number("retail_price"),
                         wholesale_per_box=self.form_number("wholesale_price"),
                         special_discount=self.form_number("special_discount"))
        self.submit_cart_item()
        return line

    @allure.step("Add Opening Stock line from spec")
    def add_opening_line(self, spec, batch: str):
        """Opening Stock counterpart of ``add_line``. Order matters because BTP + VAT/Box is derived: Retail
        Price/Box first, then the Opening Stock % (when the spec gives one), then - only for a manual override -
        BTP + VAT/Box (editing Retail or the % afterwards would re-derive it - accepted behaviour). Returns the oracle
        ``Line`` built from what the FORM held."""
        from utils.inventory_calc import Line
        product = self.resolve_product(spec.product)
        self.select_product(product, exact=True)
        if spec.retail is not None:
            self.set_value("retail_price", spec.retail)
            self.field("retail_price").blur()
            self.page.wait_for_timeout(250)
        if spec.opening_pct is not None:
            self.set_value("opening_stock_percent", spec.opening_pct)
            self.field("opening_stock_percent").blur()
            self.page.wait_for_timeout(250)
        if spec.btp_vat_per_box is not None:
            self.set_value("price_per_box", spec.btp_vat_per_box)
            self.field("price_per_box").blur()
            self.page.wait_for_timeout(250)
        self.set_value("box_qty", spec.box_qty)
        self.field("box_qty").blur()
        if spec.free_qty:
            self.set_value("free_qty", spec.free_qty)
        if spec.wholesale is not None:
            self.set_value("wholesale_price", spec.wholesale)
        if spec.min_qty is not None:
            self.set_value("min_qty", spec.min_qty)
        if spec.rack is not None:
            self.set_value("rack_no", spec.rack)
        self.set_value("batch_no", spec.batch or batch)
        if spec.barcode:
            self.set_value("barcode_value", spec.barcode)
        if spec.expiry:
            self.set_expiry_date(*spec.expiry)
        if spec.special:
            self.type_value("special_discount", str(spec.special))
        line = Line(name=product, box_qty=self.form_number("box_qty"), qty_per_box=self.form_number("qty_per_box"),
                    btp_vat_per_box=self.form_number("price_per_box"), free_qty=self.form_number("free_qty"),
                    retail_per_box=self.form_number("retail_price"),
                    wholesale_per_box=self.form_number("wholesale_price"),
                    special_discount=self.form_number("special_discount"))
        self.submit_cart_item()
        return line

    def form_errors(self) -> list[str]:
        """Inline validation messages under the form fields (e.g. 'This product is already in the cart')."""
        return [t.strip() for t in self.page.locator(".ant-form-item-explain-error").all_inner_texts() if t.strip()]

    def messages(self) -> list[str]:
        """Toasts AND inline form errors."""
        return self.toast_messages() + self.form_errors()

    def try_add_to_cart(self) -> bool:
        """Click Add Items to Cart for the form as it stands; True if the cart grew (the form accepted the item)."""
        before = self.total_items()
        self.click(self.submit_button(), description="try Add Items to Cart")
        return self._poll(lambda: self.total_items() > before, timeout=3_000)

    def try_add_line(self, spec, batch: str) -> tuple[bool, list[str]]:
        """Fill the form from ``spec`` and click Add Items to Cart WITHOUT assuming success.
        Returns (item_was_added, toast messages shown)."""
        self.select_product(self.resolve_product(spec.product), exact=True)
        self.set_value("box_qty", spec.box_qty)
        self.set_value("batch_no", spec.batch or batch)
        before = self.total_items()
        seen: list[str] = []
        self.click(self.submit_button(), description="try Add Items to Cart")

        def _added() -> bool:
            for t in self.messages():             # toasts are transient: collect on every poll, not once at the end
                if t not in seen:
                    seen.append(t)
            return self.total_items() > before

        added = self._poll(_added, timeout=4_000)
        return added, seen

    # symbolic product ("P0".."P2") -> catalogue name; set by the fixture
    product_catalogue: list[str] = []

    def resolve_product(self, ref: str) -> str:
        if ref.startswith("P") and ref[1:].isdigit() and self.product_catalogue:
            return self.product_catalogue[int(ref[1:]) % len(self.product_catalogue)]
        return ref

    # ------------------------------------------------------------------ cart reads
    def cart_rows(self) -> list[dict[str, str]]:
        """Every cart row as {header: cell text}; the Action column is dropped."""
        headers = self.cart.headers()
        rows = []
        for i in range(self.cart.row_count()):
            cells = self.cart.rows.nth(i).locator("td").all_inner_texts()
            rows.append({h: c.strip() for h, c in zip(headers, cells) if h and h != "Action"})
        return rows

    def cart_total_price(self) -> float:
        from utils.helpers import money
        return money(self.cart_total_price_text())

    def clear_cart(self) -> None:
        """Delete every row (carts persist per mode across navigations)."""
        while self.cart_row_count() > 0:
            self.delete_cart_row(self.cart_row(0))

    def total_items(self) -> int:
        txt = self.page.get_by_text("Total Items", exact=True).locator("xpath=following-sibling::*[1]").inner_text()
        m = re.search(r"\d+", txt)
        return int(m.group()) if m else 0

    def cart_total_price_text(self) -> str:
        return self.cart_total_root.locator("span").nth(1).inner_text().strip()

    def cart_is_empty(self) -> bool:
        return self.cart.is_empty()

    def cart_row(self, index: int) -> Locator:
        return self.cart.rows.nth(index)

    def cart_row_by_text(self, text: str) -> Locator:
        return self.cart.row_by_text(text)

    def cart_row_count(self) -> int:
        return self.cart.row_count()

    # Action icons: the last <td> holds 2 clickable divs, edit (pencil) first,
    # delete (red trash) second - no accessible name on either.
    def _row_action(self, row: Locator, index: int) -> Locator:
        return row.locator("td").last.locator("div[style*='cursor: pointer']").nth(index)

    def cart_row_action_accessibility(self, row: Locator, index: int) -> dict[str, str | None]:
        """role / aria-label / tabindex for one row action icon (edit=0,
        delete=1) - used to prove/disprove keyboard + screen-reader
        reachability (BUG-INV-013). A real button, or a div with
        role='button' + tabindex='0' + a non-empty aria-label, passes;
        all-None fails (not in the tab order, no accessible name)."""
        el = self._row_action(row, index)
        return {
            "tag": el.evaluate("e => e.tagName"),
            "role": el.get_attribute("role"),
            "aria_label": el.get_attribute("aria-label"),
            "tabindex": el.get_attribute("tabindex"),
        }

    @allure.step("Edit cart row")
    def edit_cart_row(self, row: Locator) -> None:
        self.click(self._row_action(row, 0), expect_effect=self.is_edit_mode, description="edit cart row")

    @allure.step("Delete cart row")
    def delete_cart_row(self, row: Locator) -> None:
        before = self.total_items()
        self.click(self._row_action(row, 1), description="delete cart row")
        self._poll(lambda: self.total_items() < before, timeout=6_000)

    # ------------------------------------------------------------------ hold / resume
    def hold_list_count(self) -> int:
        txt = self.hold_list_btn.inner_text()
        m = re.search(r"\d+", txt)
        return int(m.group()) if m else 0

    @allure.step("Hold current inventory")
    def hold_current_inventory(self) -> None:
        self.click(self.hold_current_btn, expect_effect=lambda: self.total_items() == 0,
                   description="Hold Current Inventory")

    def open_hold_list(self) -> "HoldListDialog":
        dlg = HoldListDialog(self.page, self.click)
        self.click(self.hold_list_btn, expect_effect=dlg.is_open, description="open Hold List")
        return dlg

    @allure.step("Go to Inventory Checkout")
    def go_to_checkout(self):
        from pages.inventory_checkout_page import InventoryCheckoutPage
        self.click(self.go_to_checkout_btn, description="Go to Inventory Checkout")
        return InventoryCheckoutPage(self.page).wait_loaded()


class HoldListDialog:
    """The 'Hold List' modal opened from the Inventory page."""

    def __init__(self, page: Page, clicker):
        self.page = page
        self._click = clicker
        self.root = page.get_by_role("dialog", name="Hold List")
        self.table = DataTable(page, root=self.root)

    def is_open(self) -> bool:
        return self.root.count() > 0 and self.root.is_visible()

    def count(self) -> int:
        txt = self.root.get_by_text("Total Hold List").locator("xpath=following-sibling::*[1]").inner_text()
        m = re.search(r"\d+", txt)
        return int(m.group()) if m else 0

    def _row_action(self, row: Locator, index: int) -> Locator:
        return row.locator("td").last.locator("div[style*='cursor: pointer']").nth(index)

    def resume(self, index: int = 0) -> None:
        row = self.table.rows.nth(index)
        self._click(self._row_action(row, 0), expect_effect=lambda: not self.is_open(), description="resume hold")

    def delete(self, index: int = 0) -> None:
        before = self.count()
        row = self.table.rows.nth(index)
        self._click(self._row_action(row, 1), description="delete hold")

    def close(self) -> None:
        self._click(self.root.locator(".ant-modal-close, [aria-label='Close']").first,
                    expect_effect=lambda: not self.is_open(), description="close Hold List")
