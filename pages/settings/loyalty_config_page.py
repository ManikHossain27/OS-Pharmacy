"""Settings > Loyalty Config (route /settings/loyalty-config): four numbers per pharmacy.

  Earning Rule        "Every [Tk] purchase = 1 point"      (earningRuleAmount)
  Redemption Rule     "[points] = 1 Tk"                    (redemptionRulePoint)
  Minimum Redeem Points                                    (minRedeemPoint)
  Max Redeem Limit per Transaction                         (maxRedeemPoint)

Buttons: Cancel, Save Changes (PUT loyalty-program-configs/update/{pharmacy}). The inputs have generated ids, so they are
addressed by position. Typing must use the keyboard - a plain ``fill`` does not reach the form model.
"""
from __future__ import annotations

import allure

from pages.base_page import BasePage

FIELDS = ("earning", "redemption", "min_redeem", "max_redeem")


class LoyaltyConfigPage(BasePage):
    ROUTE = "/settings/loyalty-config"

    def __init__(self, page):
        super().__init__(page)
        self.inputs = page.locator("main input")
        self.save_btn = page.get_by_role("button", name="Save Changes")
        self.cancel_btn = page.get_by_role("button", name="Cancel")

    @allure.step("Open Loyalty Config")
    def open(self, route: str | None = None) -> "LoyaltyConfigPage":
        self.page.goto(self.ROUTE)
        self.inputs.nth(3).wait_for(state="visible", timeout=120_000)
        for _ in range(40):                         # stored values arrive after the form renders
            if self.inputs.nth(0).input_value().strip():
                break
            self.page.wait_for_timeout(500)
        self.page.wait_for_timeout(1_500)
        return self

    def labels(self) -> str:
        return self.page.locator("main").inner_text()

    def values(self) -> dict[str, str]:
        return {name: self.inputs.nth(i).input_value().strip() for i, name in enumerate(FIELDS)}

    def set(self, **fields) -> "LoyaltyConfigPage":
        """Type values, e.g. ``set(earning=100, redemption=10, min_redeem=50, max_redeem=500)``."""
        for name, text in fields.items():
            box = self.inputs.nth(FIELDS.index(name))
            box.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            if str(text) != "":
                self.page.keyboard.type(str(text), delay=30)
        return self

    def save(self) -> tuple[int | None, str, str]:
        """Click Save Changes; (status, request body, toast/validation text). status None = no request was sent."""
        status, body = None, ""
        try:
            with self.page.expect_response(lambda r: r.request.method == "PUT" and "loyalty-program-configs" in r.url,
                                           timeout=6_000) as info:
                self.save_btn.click()
            status, body = info.value.status, info.value.request.post_data or ""
        except Exception:
            pass
        self.page.wait_for_timeout(800)
        text = " | ".join(self.toast_messages() + self.form_errors())
        return status, body, text
