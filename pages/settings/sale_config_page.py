"""Settings > Sale Config (route /settings/sale-config): seven POS toggles and the Business Type switch.

Toggle ids: outOfStockSale, allowLossSale, stockQty, companyName, profitMargin, rackNo, separateCashier; ``businessType`` is a
switch whose ON state is Retail. Buttons: Cancel, Save Changes. The config is per pharmacy and shared by every user of it, so
tests snapshot it first and put it back with ``restore`` (see tests/settings/conftest.py).
"""
from __future__ import annotations

import allure

from pages.base_page import BasePage

TOGGLES = ("outOfStockSale", "allowLossSale", "stockQty", "companyName", "profitMargin", "rackNo", "separateCashier")


class SaleConfigPage(BasePage):
    ROUTE = "/settings/sale-config"

    def __init__(self, page):
        super().__init__(page)
        self.save_btn = page.get_by_role("button", name="Save Changes")
        self.cancel_btn = page.get_by_role("button", name="Cancel")

    @allure.step("Open Sale Config")
    def open(self, route: str | None = None) -> "SaleConfigPage":
        self.page.goto(self.ROUTE)
        self.page.locator("#outOfStockSale").wait_for(state="visible", timeout=120_000)
        self.page.wait_for_timeout(2_000)           # the stored values arrive after the form renders
        return self

    def toggle(self, name: str) -> "SaleConfigPage":
        self.page.locator(f"#{name}").click()
        return self

    def is_on(self, name: str) -> bool:
        return self.page.locator(f"#{name}").get_attribute("aria-checked") == "true"

    def state(self) -> dict[str, bool]:
        """Every toggle plus ``retail`` (True = Business Type Retail)."""
        out = {name: self.is_on(name) for name in TOGGLES}
        out["retail"] = self.is_on("businessType")
        return out

    def set_state(self, wanted: dict[str, bool]) -> "SaleConfigPage":
        """Click only the switches whose current value differs (does not save)."""
        for name, value in wanted.items():
            ident = "businessType" if name == "retail" else name
            if self.is_on(ident) != value:
                self.page.locator(f"#{ident}").click()
        return self

    def save(self) -> tuple[int | None, str]:
        """Click Save Changes once; (status, request body) of the PUT sales-configs/update call."""
        def _is_update(resp) -> bool:
            return resp.request.method == "PUT" and "sales-configs" in resp.url

        with self.page.expect_response(_is_update, timeout=30_000) as info:
            self.save_btn.click()
        resp = info.value
        return resp.status, resp.request.post_data or ""

    def double_click_save(self) -> list[int]:
        """Double-click Save Changes; statuses of every PUT sales-configs call seen within 6 s."""
        seen: list[int] = []

        def _on(resp) -> None:
            if resp.request.method == "PUT" and "sales-configs" in resp.url:
                seen.append(resp.status)

        self.page.on("response", _on)
        try:
            self.save_btn.dblclick()
            self.page.wait_for_timeout(6_000)
        finally:
            self.page.remove_listener("response", _on)
        return seen

    @allure.step("Save Sale Config {wanted}")
    def apply(self, wanted: dict[str, bool]) -> dict[str, bool]:
        """Open, set the given switches, save, reload and return the persisted state."""
        self.open().set_state(wanted)
        status, body = self.save()
        assert status is not None and status < 300, f"saving {wanted} failed: {status} {body[:200]}"
        return self.open().state()
