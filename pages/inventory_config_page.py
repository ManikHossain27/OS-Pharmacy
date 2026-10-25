"""Settings > Inventory Config (route /settings/inventory-config): the pharmacy's VAT Percentage (used by TP/VAT mode to
pre-fill VAT/Box = TP x %) and Opening Stock Percentage (used by Opening Stock mode: BTP+VAT/Box = Retail x (1 - %)).
Defaults 17.4 and 12. Buttons: Cancel, Save Changes."""
from __future__ import annotations

import allure

from pages.base_page import BasePage


class InventoryConfigPage(BasePage):
    ROUTE = "/settings/inventory-config"

    def __init__(self, page):
        super().__init__(page)
        self.vat = page.locator("#vatPercentage")
        self.opening = page.locator("#openingStockPercentage")
        self.save_btn = page.get_by_role("button", name="Save Changes")
        self.cancel_btn = page.get_by_role("button", name="Cancel")

    @allure.step("Open Inventory Config")
    def open(self, route: str | None = None) -> "InventoryConfigPage":
        self.page.goto(self.ROUTE)
        return self.wait_loaded()

    def wait_loaded(self) -> "InventoryConfigPage":
        self.vat.wait_for(state="visible", timeout=120_000)
        for _ in range(60):                       # the stored values arrive after the form renders
            if self.vat.input_value().strip() and self.opening.input_value().strip():
                break
            self.page.wait_for_timeout(500)
        return self

    # ------------------------------------------------------------------ values
    def values(self) -> tuple[str, str]:
        return self.vat.input_value().strip(), self.opening.input_value().strip()

    def numbers(self) -> tuple[float, float]:
        v, o = self.values()
        return float(v), float(o)

    def _type(self, field, text) -> None:
        field.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        if str(text) != "":
            self.page.keyboard.type(str(text), delay=20)

    def set_vat(self, text) -> None:
        self._type(self.vat, text)

    def set_opening(self, text) -> None:
        self._type(self.opening, text)

    def required_labels(self) -> list[str]:
        return [t.strip() for t in self.page.locator(".ant-form-item-required").all_inner_texts()]

    # ------------------------------------------------------------------ actions
    def toast_text(self) -> str:
        loc = self.page.locator(".ant-message, .ant-notification, .Toastify, [role=alert]")
        try:
            loc.first.wait_for(state="visible", timeout=6_000)
            return " | ".join(t.strip() for t in loc.all_inner_texts() if t.strip())
        except Exception:
            return ""

    @allure.step("Save Changes")
    def save(self) -> tuple[int | None, str, str]:
        """(status, body, toast) of the request Save Changes sends (None, '', toast) when no write request leaves the page."""
        def _write(resp) -> bool:
            return resp.request.method in ("POST", "PUT", "PATCH") and "/secured/" in resp.url

        try:
            with self.page.expect_response(_write, timeout=15_000) as info:
                self.save_btn.click()
            resp = info.value
            status, body = resp.status, resp.text()
        except Exception:
            status, body = None, ""
        return status, body, self.toast_text()

    def save_enabled(self) -> bool:
        return self.save_btn.is_enabled()

    def cancel(self) -> None:
        self.cancel_btn.click()
        self.page.wait_for_timeout(1500)

    def save_values(self, vat=None, opening=None) -> tuple[int | None, str, str]:
        if vat is not None:
            self.set_vat(vat)
        if opening is not None:
            self.set_opening(opening)
        return self.save()
