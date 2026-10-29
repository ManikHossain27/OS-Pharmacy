"""Sale (route /sale) and Sale Checkout (route /sale-checkout) - only what the Inventory Return suite needs: sell pieces / boxes
of a product so the stock a return can draw on goes down.

The Sale form has no batch picker: the product is chosen by name (its option shows the product's total stock) and the
system takes the pieces from its batches. Checkout: optional walk-in customer detail, paid amount + payment method,
Complete Sale.
"""
from __future__ import annotations

import re

import allure

from pages.base_page import BasePage

OPTION = ".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option"


def _num(text: str) -> float:
    m = re.search(r"-?[\d,]+(?:\.\d+)?", text or "")
    return float(m.group().replace(",", "")) if m else float("nan")


class SalePage(BasePage):
    ROUTE = "/sale"

    def __init__(self, page):
        super().__init__(page)
        self.product_input = page.locator("#productId")
        self.qty_input = page.locator("#qty")
        self.add_btn = page.get_by_role("button", name="Add to Cart")
        self.checkout_btn = page.get_by_role("button", name="Go to Sale Checkout")
        self.complete_btn = page.get_by_role("button", name="Complete Sale")

    @allure.step("Open Sale")
    def open(self, route: str | None = None) -> "SalePage":
        self.page.goto(self.ROUTE)
        self.product_input.wait_for(state="attached", timeout=120_000)
        self.page.wait_for_timeout(1500)
        self.clear_cart()
        return self

    def cart_count(self) -> int:
        return self.page.locator("tbody tr.ant-table-row").count()

    def clear_cart(self) -> None:
        """Delete any lines a previous (failed) test left in the Sale cart."""
        for _ in range(20):
            if not self.cart_count():
                return
            row = self.page.locator("tbody tr.ant-table-row").first
            buttons = row.locator("button, svg").all()
            if not buttons:
                return
            buttons[-1].click(force=True)
            self.page.wait_for_timeout(600)

    # ------------------------------------------------------------------ product
    def product_options(self, term: str) -> list[str]:
        self.product_input.click(force=True)
        self.page.keyboard.press("Control+A")
        self.page.keyboard.type(term, delay=40)
        self.page.wait_for_timeout(3000)
        return [o.inner_text().replace("\n", " | ").strip() for o in self.page.locator(OPTION).all()]

    def stock_in_dropdown(self, term: str) -> tuple[float, float]:
        """(pieces, boxes) the product's option shows in the search dropdown ('28,985 | pcs | 483.08 box')."""
        first = self.product_options(term)[0]
        m = re.search(r"(-?[\d,]+(?:\.\d+)?)\s*\|\s*pcs?\s*\|\s*(-?[\d,]+(?:\.\d+)?)\s*box", first)
        assert m, f"no stock in the option text: {first!r}"
        self.page.keyboard.press("Escape")
        return float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))

    def select_product(self, term: str, named: str | None = None) -> None:
        """Pick the first option; with ``named`` wait for (and pick) the first option containing that text - the dropdown can
        briefly show the previous search's results."""
        self.product_options(term)
        option = self.page.locator(OPTION).filter(has_text=named).first if named else self.page.locator(OPTION).first
        option.wait_for(state="visible", timeout=30_000)
        option.click()
        self.page.wait_for_timeout(1500)

    # ------------------------------------------------------------------ cart
    def set_unit(self, unit: str) -> None:
        select = self.page.locator("#qtyUnitType").locator("xpath=ancestor::div[contains(@class,'ant-select')][1]")
        if unit.lower().startswith("box") != ("box" in select.inner_text().lower()):
            select.click()
            self.page.locator(OPTION).filter(has_text=re.compile("box" if unit.lower().startswith("box") else "pc", re.I)).first.dispatch_event("click")

    def add_line(self, product: str, qty, unit: str = "pc", price=None, discount_pct=None, named: str | None = None) -> None:
        """Add a cart line. ``price`` overrides the per-piece/per-box sale price; ``discount_pct`` is a line discount in %."""
        self.select_product(product, named=named)
        self.set_unit(unit)
        self.qty_input.fill(str(qty))
        if price is not None:
            self.page.locator("#retailPrice, #retailPricePerBox").first.fill(str(price))
        if discount_pct is not None:
            self.page.locator("#discountValue").fill(str(discount_pct))
        self.add_btn.click()
        self.page.wait_for_timeout(1500)

    def go_to_checkout(self) -> "SalePage":
        self.checkout_btn.click()
        self.page.wait_for_url("**/sale-checkout", timeout=60_000)
        self.complete_btn.wait_for(state="visible", timeout=60_000)
        return self

    def complete(self) -> tuple[int | None, str]:
        """Click Complete Sale once; (status, body) of the sale POST (None when no request is sent)."""
        def _is_sale(resp) -> bool:
            return resp.request.method == "POST" and "sale" in resp.url.lower() and "/secured/" in resp.url

        try:
            with self.page.expect_response(_is_sale, timeout=30_000) as info:
                self.complete_btn.click()
            resp = info.value
            return resp.status, resp.text()
        except Exception:
            return None, ""

    # ------------------------------------------------------------------ hold
    def hold_count(self) -> int:
        """The Hold List badge (0 when none)."""
        m = re.search(r"(\d+)\s*Hold List", self.page.locator("main").inner_text())
        return int(m.group(1)) if m else 0

    def hold_double_click(self) -> int:
        """Double-click Hold Current Sale; the Hold List badge afterwards."""
        self.page.get_by_role("button", name="Hold Current Sale").dblclick()
        self.page.wait_for_timeout(6_000)
        return self.hold_count()

    def clear_holds(self) -> None:
        """Delete every held sale (Hold List > Clear all > confirm)."""
        if not self.hold_count():
            return
        self.page.get_by_text("Hold List").first.click()
        self.page.get_by_role("button", name="Clear all").click(timeout=15_000)
        confirm = self.page.get_by_role("button", name=re.compile("Yes"))
        confirm.last.wait_for(state="visible", timeout=10_000)
        confirm.last.focus()
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(3_000)

    @allure.step("Sell {qty} {unit} of {product}")
    def sell(self, product: str, qty, unit: str = "pc") -> tuple[int | None, str]:
        self.open()
        self.add_line(product, qty, unit)
        self.go_to_checkout()
        return self.complete()
