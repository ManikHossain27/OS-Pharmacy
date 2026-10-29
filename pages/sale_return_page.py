"""Sale Return (route /sale-return?saleId=...): reached from Sale Record > Row Actions > Return Sale.

Each line has a Return Qty input (placeholder "0"); 'Go to Return Checkout' opens the Return Checkout drawer whose button
'Complete Sale Return' posts POST sales/return/{saleId}/{pharmacy}. The server refuses a quantity above what is left on the line.
"""
from __future__ import annotations

import re

import allure

from pages.base_page import BasePage


class SaleReturnPage(BasePage):
    ROUTE = "/sale-return"

    def __init__(self, page):
        super().__init__(page)
        self.qty_inputs = page.locator("main input[placeholder='0']")
        self.checkout_btn = page.get_by_role("button", name="Go to Return Checkout")
        self.complete_btn = page.get_by_role("button", name="Complete Sale Return")

    @allure.step("Open Return Sale for the top Sale Record row")
    def open_from_record(self, sale_record, index: int = 0) -> "SaleReturnPage":
        """``sale_record`` is an opened SaleRecordPage; uses the row's action menu."""
        sale_record.open_row_action(index, "Return Sale")
        self.qty_inputs.first.wait_for(state="visible", timeout=90_000)
        self.page.wait_for_timeout(3_000)
        return self

    def set_return_qty(self, line: int, qty) -> "SaleReturnPage":
        self.qty_inputs.nth(line).fill(str(qty))
        self.page.wait_for_timeout(2_000)
        return self

    def go_to_return_checkout(self) -> "SaleReturnPage":
        self.checkout_btn.click()
        self.complete_btn.wait_for(state="visible", timeout=30_000)
        self.page.wait_for_timeout(1_000)
        return self

    def qty_value(self, line: int) -> str:
        return self.qty_inputs.nth(line).input_value()

    def refund_preview(self) -> float:
        """The 'Return to Customer Tk n' figure at the bottom of the return screen."""
        text = self.page.locator("main").inner_text().replace("\n", " ")
        m = re.search(r"Return to Customer\s*Tk\s*(-?[\d,]+(?:\.\d+)?)", text)
        return float(m.group(1).replace(",", "")) if m else float("nan")

    def checkout_figures(self) -> dict[str, float]:
        """Return Checkout drawer: Return Price, Exchange Price, Return to Customer, Total Price (was), Revised Price."""
        text = self.page.locator("[role=dialog]:visible").last.inner_text().replace("\n", " ")
        out: dict[str, float] = {}
        for label in ("Return Price", "Exchange Price", "Return to Customer", "Total Price (was)", "Revised Price"):
            m = re.search(re.escape(label) + r"\s*Tk\s*(-?[\d,]+(?:\.\d+)?)", text)
            if m:
                out[label] = float(m.group(1).replace(",", ""))
        return out

    def validation_text(self) -> str:
        return " | ".join(self.toast_messages() + self.form_errors())

    @allure.step("Complete Sale Return (single click)")
    def complete_once(self) -> tuple[int | None, str]:
        """(status, body) of the POST sales/return; None when no request was sent."""
        try:
            with self.page.expect_response(lambda r: r.request.method == "POST" and "/sales/return/" in r.url, timeout=30_000) as info:
                self.complete_btn.click()
            return info.value.status, info.value.text()
        except Exception:
            return None, ""

    @allure.step("Complete Sale Return (double click)")
    def complete_double_click(self) -> list[int]:
        """Statuses of every POST sales/return seen within 10 s of a rapid double click."""
        seen: list[int] = []

        def _on(resp) -> None:
            if resp.request.method == "POST" and "/sales/return/" in resp.url:
                seen.append(resp.status)

        self.page.on("response", _on)
        try:
            self.complete_btn.dblclick()
            self.page.wait_for_timeout(10_000)
        finally:
            self.page.remove_listener("response", _on)
        return seen
