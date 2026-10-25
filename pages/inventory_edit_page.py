"""Edit Inventory (routes: /inventory/edit/<id> -> /inventory/edit/checkout/<id>).

Reached from Inventory Record -> row menu -> Edit Inventory.  The cart screen is the Inventory page's own cart and
form (``InventoryPage``), pre-loaded with the saved lines; the checkout screen is ``InventoryCheckoutPage`` whose
Complete button reads "Update Inventory" and sends ``PUT .../inventories/update/<id>/<pharmacy>``.
"""
from __future__ import annotations

import re

import allure
from playwright.sync_api import Page

from pages.base_page import BasePage
from pages.inventory_checkout_page import InventoryCheckoutPage
from pages.inventory_page import InventoryPage
from pages.inventory_record_page import InventoryRecordPage

EDIT_URL = re.compile(r"/inventory/(?:[\w-]+/)?edit/(\d+)(?:$|\?)")   # the TP/VAT and Opening Stock routes carry a mode segment
EDIT_CHECKOUT_URL = re.compile(r"/inventory/(?:[\w-]+/)?edit/checkout/\d+")


class InventoryEditPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.cart = InventoryPage(page)
        self.update_btn = page.get_by_role("button", name="Update Inventory")

    @allure.step("Open Edit Inventory for {inventory_id}")
    def open_for(self, record: InventoryRecordPage, inventory_id: str) -> "InventoryEditPage":
        record.choose_row_action(record.row_by_inventory_id(inventory_id), "Edit Inventory")
        try:
            self.page.wait_for_url(EDIT_URL, timeout=30_000)
        except Exception as exc:
            raise AssertionError(f"Edit Inventory did not open an edit route; the page is at {self.page.url}") from exc
        self.page.get_by_text("Cart Inventory Items").wait_for(state="visible", timeout=30_000)
        self._poll(lambda: self.cart.total_items() > 0, timeout=20_000)
        title = self.heading_text()
        self.cart.mode_override = next((m for m in ("TP/VAT", "Opening Stock") if m in title), "Default")
        return self

    def heading_text(self) -> str:
        """'Edit Inventory #INV_... Default' - the page title with the record id and the mode badge."""
        return self.page.get_by_text("Edit Inventory", exact=True).first.locator("xpath=..").inner_text()

    def go_to_checkout(self) -> InventoryCheckoutPage:
        co = self.cart.go_to_checkout()
        self.page.wait_for_url(EDIT_CHECKOUT_URL, timeout=30_000)
        return co

    @allure.step("Update Inventory, capturing the update response")
    def update_capturing_response(self, co: InventoryCheckoutPage, choice: str | None = None) -> tuple[int | None, str]:
        """Click Update Inventory once (taking ``choice`` in the payment dialog when one appears) and return
        (status, body) of the PUT .../inventories/update/... response, or (None, '') when none arrives."""
        def _is_update(resp) -> bool:
            return "inventories/update/" in resp.url and resp.request.method == "PUT"

        dlg = co.payment_dialog
        try:
            with self.page.expect_response(_is_update, timeout=30_000) as info:
                self.click(self.update_btn, description="Update Inventory")
                if choice:
                    if not dlg.wait_open(10_000):
                        return None, "NO_PAYMENT_DIALOG"
                    co.last_payment_dialog = dlg.snapshot()
                    dlg.choose(choice)
            resp = info.value
        except Exception:
            return None, ""
        try:
            return resp.status, resp.text()
        except Exception:
            return resp.status, ""
