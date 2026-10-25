"""Inventory Checkout (route: /inventory-checkout).

Totals live in a stable ``.inventory-checkout-summary`` card - scoping label
lookups to it is required because generic labels like "Total Price" also
appear as a cart-table column header on this same page.
"""
from __future__ import annotations

import os

import re
from typing import Any

import allure
from playwright.sync_api import Locator, Page, expect

from components.antd_select import AntdSelect
from components.data_table import DataTable
from pages.base_page import BasePage
from utils.constants import INVENTORY_CHECKOUT_FIELDS as F
from utils.constants import ROUTES


class InventoryCheckoutPage(BasePage):
    route = ROUTES["inventory_checkout"]
    DUE_BUY, LESS_BUY, ADVANCE_BUY = "Due & Buy", "Less & Buy", "Advance & Buy"

    def __init__(self, page: Page):
        super().__init__(page)
        self.cart_table = DataTable(page)
        self.edit_cart_btn = page.get_by_role("button", name="Edit Cart Inventory items")

        # The Inventory Type control is the only select whose value is "Purchase" / "Borrowed"
        # (verified live 2026-10-07; the label text is not reliably adjacent to it).
        self.inventory_type_select = AntdSelect(
            page,
            root=page.locator("main .ant-select").filter(
                has=page.locator(".ant-select-content[title='Purchase'], .ant-select-content[title='Borrowed']")
            ).first,
            clicker=self.click,
        )
        self.supplier_select = AntdSelect(page, F["supplier"], clicker=self.click)
        self.add_new_supplier_link = page.get_by_text("Add New Supplier", exact=True)

        self.discount_value_input = page.locator(f"#{F['discount_value']}")
        self.discount_unit_select = AntdSelect(
            page, root=self._select_root_after_input(F["discount_value"]), clicker=self.click
        )

        self.paid_input = page.locator(f"#{F['paid_to_supplier']}")
        self.payment_method_select = AntdSelect(
            page, root=self._select_root_after_input(F["paid_to_supplier"]), clicker=self.click
        )

        self.invoice_number_input = page.locator(f"#{F['invoice_number']}")
        self.complete_btn = page.get_by_role("button", name="Complete Inventory")

        self.summary_root = page.locator(".inventory-checkout-summary")

    # ------------------------------------------------------------------ locator helpers
    def _select_root_after_input(self, input_id: str) -> Locator:
        row = self.page.locator(f"#{input_id}").locator("xpath=ancestor::div[2]")
        return row.locator(".ant-select")

    # ------------------------------------------------------------------ loaders
    def is_loaded(self) -> bool:
        return self.summary_root.count() > 0

    def wait_loaded(self) -> "InventoryCheckoutPage":
        expect(self.summary_root).to_be_visible(timeout=60_000)   # first visit loads the route chunk (~tens of s on the dev build)
        return self

    # ------------------------------------------------------------------ actions
    @allure.step("Select supplier {name}")
    def select_supplier(self, name: str) -> None:
        self.supplier_select.select(name, exact=False)

    def select_first_supplier(self) -> str:
        """The first supplier offered - or the one named by QA_SUPPLIER (a pharmacy whose first supplier is not wanted)."""
        self.supplier_select.open()
        wanted = os.getenv("QA_SUPPLIER")
        options = self.supplier_select._dropdown.locator(".ant-select-item-option")
        opt = options.filter(has_text=wanted).first if wanted else options.first
        text = opt.inner_text().strip()
        self.click(opt, description="select first supplier")
        return text

    @allure.step("Apply discount {value} {unit}")
    def set_discount(self, value: Any, unit: str = "%") -> None:
        self.discount_value_input.fill("")
        self.discount_value_input.fill(str(value))
        self.discount_unit_select.select(unit)

    def set_paid_amount(self, value: Any) -> None:
        self.paid_input.fill("")
        self.paid_input.fill(str(value))

    def set_payment_method(self, method: str) -> None:
        self.payment_method_select.select(method)

    def set_invoice_number(self, value: str) -> None:
        self.invoice_number_input.fill(value)

    @allure.step("Complete Inventory")
    def complete(self) -> None:
        self.click(self.complete_btn, description="Complete Inventory")

    def complete_enabled(self) -> bool:
        return self.complete_btn.is_enabled()

    @allure.step("Complete Inventory, capturing the create response")
    def complete_capturing_response(self, settle_ms: int = 8_000, choice: str | None = None) -> tuple[int | None, str]:
        """Clicks Complete Inventory once and returns (status, body) of the
        POST .../inventories/create/... response, or (None, '') if none arrives within
        ``settle_ms``. The wait is registered BEFORE the click (``expect_response``) - a
        listener plus a 'networkidle' wait can return before the request is even sent.

        When Total Paid differs from the Final Price the app interposes the payment
        decision dialog ("You paid less/more than the bill" -> Due & Buy / Less & Buy /
        Advance & Buy) and the inventory is only created after one of them is chosen:
        pass ``choice`` to pick it. Body is "NO_PAYMENT_DIALOG" / "UNEXPECTED_PAYMENT_DIALOG: ..."
        when the dialog behaviour differs from what the caller expected."""
        def _is_create(resp) -> bool:
            return "inventories/create/" in resp.url and resp.request.method == "POST"

        dlg = self.payment_dialog
        self.last_payment_dialog = None
        try:
            with self.page.expect_response(_is_create, timeout=max(settle_ms, 30_000)) as info:
                self.complete()
                if choice:
                    if not dlg.wait_open(10_000):
                        raise _NoPaymentDialog()
                    self.last_payment_dialog = dlg.snapshot()
                    dlg.choose(choice)
            resp = info.value
        except _NoPaymentDialog:
            return None, "NO_PAYMENT_DIALOG"
        except Exception:
            if not choice and dlg.is_open():
                return None, f"UNEXPECTED_PAYMENT_DIALOG: {dlg.text()[:200]!r}"
            return None, ""
        try:
            body = resp.text()
        except Exception:
            body = ""
        return resp.status, body

    @property
    def payment_dialog(self) -> "PaymentDecisionDialog":
        return PaymentDecisionDialog(self.page)

    @allure.step("Click Complete Inventory and wait for the payment decision dialog")
    def complete_expecting_dialog(self, timeout: int = 10_000) -> "PaymentDecisionDialog":
        self.complete()
        dlg = self.payment_dialog
        dlg.wait_open(timeout)
        return dlg

    @allure.step("Double-click Complete Inventory")
    def complete_double_click(self, settle_ms: int = 8_000) -> list[int]:
        """Fires two click events on Complete Inventory back-to-back (no wait
        between them, bypassing Playwright's own actionability delay) and
        returns the HTTP status of every POST .../inventories/create/...
        response observed afterwards. Used to prove/disprove double-submit
        protection (BUG-INV-012) - a properly guarded button yields exactly
        one entry here."""
        statuses: list[int] = []

        def _capture(resp) -> None:
            if "inventories/create/" in resp.url and resp.request.method == "POST":
                statuses.append(resp.status)

        self.page.on("response", _capture)
        try:
            self.page.evaluate(
                """() => {
                    const btn = Array.from(document.querySelectorAll('button'))
                        .find(b => b.textContent.trim() === 'Complete Inventory');
                    btn.click();
                    btn.click();
                }"""
            )
            try:
                self.page.wait_for_load_state("networkidle", timeout=settle_ms)
            except Exception:
                pass
        finally:
            self.page.remove_listener("response", _capture)
        return statuses

    # ------------------------------------------------------------------ reads
    def _summary_value(self, label: str) -> str:
        loc = self.summary_root.get_by_text(label, exact=True).locator("xpath=following-sibling::*[1]")
        return loc.inner_text().strip()

    # Summary-card labels as rendered by the app (verified live 2026-10-07):
    #   Total Items | Total Price (TP+VAT) | General Discount | Special Discount |
    #   Round Off | Final Price | Total Paid | Due
    def total_price(self) -> str:
        return self._summary_value("Total Price (TP+VAT)")

    def discount_amount(self) -> str:
        """'General Discount' (Default) / 'General Discount (on TP)' (TP/VAT) - the checkout-level % / Tk discount."""
        if self.summary_root.get_by_text("General Discount (on TP)", exact=True).count():
            return self._summary_value("General Discount (on TP)")
        return self._summary_value("General Discount")

    def total_tp(self) -> str:
        """TP/VAT mode only."""
        return self._summary_value("Total TP")

    def total_vat(self) -> str:
        """TP/VAT mode only."""
        return self._summary_value("Total VAT")

    def special_discount(self) -> str:
        return self._summary_value("Special Discount")

    def round_off(self) -> str:
        return self._summary_value("Round Off")

    def discount_enabled(self) -> bool:
        """The discount input is disabled when no line is eligible (all lines carry Free Qty)."""
        return self.discount_value_input.is_enabled()

    def live_discount_amount(self) -> str:
        """The preview near the discount input, before it is reflected in the summary card."""
        loc = self.page.get_by_text("Discount Amount", exact=True).locator("xpath=following-sibling::*[1]")
        return loc.inner_text().strip()

    def final_price(self) -> str:
        return self._summary_value("Final Price")

    def total_paid(self) -> str:
        return self._summary_value("Total Paid")

    def due(self) -> str:
        """Due amount; 'Tk 0' when the app shows 'Advance' instead (overpayment)."""
        if self.summary_root.get_by_text("Due", exact=True).count():
            return self._summary_value("Due")
        return "Tk 0"

    def advance(self) -> str:
        """Advance amount (shown INSTEAD of Due when Paid exceeds the Final Price); 'Tk 0' otherwise."""
        if self.summary_root.get_by_text("Advance", exact=True).count():
            return self._summary_value("Advance")
        return "Tk 0"

    def advance_label_shown(self) -> bool:
        """True if the summary panel relabels its Due row to 'Advance' when
        Paid Amount exceeds Final Price - used to prove/disprove BUG-INV-016
        (spec requires an overpayment be recorded as Supplier Advance, not a
        negative Due)."""
        return self.summary_root.get_by_text("Advance", exact=True).count() > 0

    # ------------------------------------------------------------------ typed reads / extra actions
    def cart_rows(self) -> list[dict[str, str]]:
        """Checkout's own item table as {header: text} (Action column dropped)."""
        headers = self.cart_table.headers()
        out = []
        for i in range(self.cart_table.row_count()):
            cells = self.cart_table.rows.nth(i).locator("td").all_inner_texts()
            out.append({h: c.strip() for h, c in zip(headers, cells) if h and h != "Action"})
        return out

    def summary(self) -> dict[str, float]:
        """Summary-card figures as numbers (Total Price, Discount Amount, Final Price, Total Paid, Due)."""
        from utils.helpers import money
        return {k: money(v) for k, v in self.totals().items()}

    INVENTORY_TYPE_LABELS = {"Purchase": "Purchase", "Borrow": "Borrowed", "Borrowed": "Borrowed"}

    def inventory_type(self) -> str:
        return self.inventory_type_select.selected_text()

    def inventory_type_options(self) -> list[str]:
        return self.inventory_type_select.options()

    @allure.step("Select Inventory Type {name}")
    def select_inventory_type(self, name: str) -> None:
        """``name`` may be the spec wording ('Borrow') - the UI option is labelled 'Borrowed'."""
        self.inventory_type_select.select(self.INVENTORY_TYPE_LABELS.get(name, name))

    def supplier_selected(self) -> bool:
        """The app keeps the last chosen supplier across navigation AND reloads and offers no clear control."""
        return self.supplier_select.has_value()

    def clear_discount(self) -> None:
        self.discount_value_input.fill("")

    def reset_discount(self) -> None:
        """Back to 'no discount': the checkout page keeps the previous discount (value AND unit) while the
        browser session is shared, so a 'no discount' scenario must clear it explicitly."""
        if not self.discount_enabled():
            return
        if self.discount_value_input.input_value().strip() not in ("", "0"):
            self.discount_value_input.fill("")
            self.discount_value_input.fill("0")
            self.discount_value_input.blur()
            self.page.wait_for_timeout(300)

    def edit_cart(self):
        """Back to the Inventory page to change the cart ('Edit Cart Inventory items')."""
        from pages.inventory_page import InventoryPage
        self.click(self.edit_cart_btn, description="Edit Cart Inventory items")
        return InventoryPage(self.page).wait_loaded()

    def tpvat_totals(self) -> dict[str, float]:
        """Summary-card figures of a TP/VAT checkout as numbers (adds Total TP and Total VAT)."""
        from utils.helpers import money
        out = self.summary()
        out["total_tp"] = money(self.total_tp())
        out["total_vat"] = money(self.total_vat())
        return out

    def totals(self) -> dict[str, str]:
        return {
            "total_price": self.total_price(),
            "discount_amount": self.discount_amount(),
            "special_discount": self.special_discount(),
            "round_off": self.round_off(),
            "final_price": self.final_price(),
            "total_paid": self.total_paid(),
            "due": self.due(),
            "advance": self.advance(),
        }


class InventoryCompleteModal:
    """Spec 42.1 'Inventory Complete' success modal (Invoice / Hold List / New Inventory).
    BUG-INV-002: the current build shows no such modal - tests assert the spec."""

    FIELDS = ("Inventory ID", "Payment Status", "Inventory Type", "Total Items", "Total Price",
              "Discount", "Final Price", "Total Paid", "Due Amount")
    ACTIONS = ("Invoice", "Hold List", "New Inventory")

    def __init__(self, page: Page):
        self.page = page
        self.root = page.get_by_role("dialog").filter(has_text=re.compile("Inventory Complete", re.I))

    def is_open(self) -> bool:
        return self.root.count() > 0 and self.root.first.is_visible()

    def wait_open(self, timeout: int = 8_000) -> bool:
        try:
            expect(self.root.first).to_be_visible(timeout=timeout)
            return True
        except Exception:
            return False

    def missing_fields(self) -> list[str]:
        return [f for f in self.FIELDS if self.root.get_by_text(f, exact=False).count() == 0]

    def missing_actions(self) -> list[str]:
        return [a for a in self.ACTIONS if self.root.get_by_role("button", name=re.compile(a, re.I)).count() == 0
                and self.root.get_by_text(a, exact=False).count() == 0]

    def has_details_link(self) -> bool:
        return self.root.get_by_text(re.compile("Inventory Details|Details", re.I)).count() > 0


class _NoPaymentDialog(Exception):
    pass


class PaymentDecisionDialog:
    """The dialog shown by Complete Inventory when Total Paid != Final Price (verified live 2026-10-11).

    Paid LESS than the bill  -> "You paid less than the bill"  with two options:
        Due & Buy    "Due: Tk X"  - X becomes a Due owed to the supplier, pay later
        Less & Buy   "Less: Tk X" - the unpaid X is waived by the supplier; the products cost less
    Paid MORE than the bill  -> "You paid more than the bill" with one option:
        Advance & Buy "Advance: Tk X" - the extra X becomes an Advance held by the supplier
    """
    TITLE = re.compile(r"You paid (less|more) than the bill", re.I)
    DUE, LESS, ADVANCE = "Due & Buy", "Less & Buy", "Advance & Buy"

    def __init__(self, page: Page):
        self.page = page
        self.root = page.locator(".ant-modal, [role=dialog]").filter(has_text=self.TITLE).last

    def is_open(self) -> bool:
        return self.root.count() > 0 and self.root.is_visible()

    def wait_open(self, timeout: int = 8_000) -> bool:
        try:
            expect(self.root).to_be_visible(timeout=timeout)
            return True
        except Exception:
            return False

    def wait_closed(self, timeout: int = 5_000) -> bool:
        try:
            expect(self.root).to_be_hidden(timeout=timeout)
            return True
        except Exception:
            return False

    def text(self) -> str:
        return self.root.inner_text()

    def kind(self) -> str | None:
        m = self.TITLE.search(self.text()) if self.is_open() else None
        return m.group(1).lower() if m else None

    def _amount_after(self, label: str) -> float | None:
        m = re.search(rf"{label}\s*Tk\s*([\d,]+(?:\.\d+)?)", self.text(), re.I)
        return float(m.group(1).replace(",", "")) if m else None

    def bill(self) -> float | None:
        return self._amount_after("BILL")

    def paid(self) -> float | None:
        return self._amount_after("YOU PAID")

    def gap(self) -> float | None:
        """SHORT BY (paid less) or EXTRA (paid more)."""
        return self._amount_after("SHORT BY") if self.kind() == "less" else self._amount_after("EXTRA")

    def snapshot(self) -> dict:
        return {"kind": self.kind(), "bill": self.bill(), "paid": self.paid(), "gap": self.gap(),
                "options": self.options(), "text": self.text()}

    def options(self) -> list[str]:
        return [t.strip() for t in self.root.get_by_role("button").all_inner_texts() if "buy" in t.lower()]

    def choose(self, label: str) -> None:
        self.root.get_by_role("button", name=label, exact=True).click()

    def dismiss(self) -> bool:
        """Close without choosing (Escape); True when the dialog is gone."""
        self.page.keyboard.press("Escape")
        return self.wait_closed()
