"""'Add New Product' right-side drawer.

Field map (captured live 2026-09-08):

  productName*(text)  strength(text)  productType*(select)  company*(select,+add)
  generic(select,+add)  quantityInBox*(number)  lastPurchasePricePerBox(number,DISABLED)
  retailPricePerBox*(number)  wholesalePricePerBox*(number)  medicine(checkbox, default on)
  --- Additional Information (collapsed) ---
  rackNo(number)  barcodeValue(text)  volume(text)  origin(select)

* = required (aria-required + validated on submit)
"""
from __future__ import annotations

import re
from typing import Any

import allure
from playwright.sync_api import Locator, Page, expect

from components.antd_select import AntdSelect
from components.side_drawer import SideDrawer
from pages.base_page import BasePage
from utils.constants import ADD_PRODUCT_FIELDS as F


class AddCompanyMiniForm:
    """The tiny 'add company' form that opens from the green [+] next to Company."""

    def __init__(self, page: Page, clicker):
        self.page = page
        self._click = clicker
        # Renders as a nested modal/drawer/popover on top of the product drawer.
        self.root = page.locator(".ant-modal-content, .ant-drawer-content").last

    def wait(self) -> "AddCompanyMiniForm":
        expect(self.root).to_be_visible(timeout=6_000)
        return self

    def name_input(self) -> Locator:
        return self.root.get_by_role("textbox").first

    def fill_name(self, value: str) -> None:
        self.name_input().fill(value)

    def save(self) -> None:
        self._click(
            self.root.get_by_role("button", name=re.compile(r"save|add|confirm|create", re.I)).last,
            description="save new company",
        )

    def cancel(self) -> None:
        self._click(self.root.get_by_role("button", name="Cancel"), description="cancel new company")

    def errors(self) -> list[str]:
        return [t.strip() for t in self.root.locator(".ant-form-item-explain-error, .ant-form-item-explain").all_inner_texts() if t.strip()]


class AddProductPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.drawer = SideDrawer(page, title="Add New Product")
        self.product_type = AntdSelect(page, F["product_type"], clicker=self.click)
        self.company = AntdSelect(page, F["company"], clicker=self.click)
        self.generic = AntdSelect(page, F["generic"], clicker=self.click)
        self.origin = AntdSelect(page, F["origin"], clicker=self.click)

    # ------------------------------------------------------------------ open/close
    def is_open(self) -> bool:
        return self.drawer.is_open()

    def wait_open(self) -> "AddProductPage":
        self.drawer.wait_open()
        return self

    def close(self) -> None:
        self.drawer.cancel(self.click)
        self.drawer.wait_closed()

    # ------------------------------------------------------------------ fields
    def _field(self, key: str) -> Locator:
        return self.drawer.field(F[key])

    def set_text(self, key: str, value: Any) -> None:
        self.fill(self._field(key), value, description=key)

    def set_number(self, key: str, value: Any) -> None:
        loc = self._field(key)
        loc.fill("")
        loc.fill(str(value))

    def toggle_medicine(self, checked: bool) -> None:
        box = self._field("medicine")
        if box.is_checked() != checked:
            self.click(box, description="Medicine checkbox")

    def expand_additional_info(self) -> None:
        header = self.drawer.root.get_by_text("Additional Information", exact=True)
        self.click(
            header,
            expect_effect=lambda: self._field("rack_no").count() > 0
            and self._field("rack_no").is_visible(),
            description="expand Additional Information",
        )

    # ------------------------------------------------------------------ high level
    @allure.step("Fill Add-Product form")
    def fill_form(self, data: dict[str, Any]) -> None:
        if "product_name" in data:
            self.set_text("product_name", data["product_name"])
        if data.get("strength") is not None:
            self.set_text("strength", data["strength"])
        if data.get("product_type"):
            self.product_type.select(data["product_type"])
        if data.get("company"):
            self.company.select(data["company"])
        if data.get("generic"):
            self.generic.select(data["generic"])
        if data.get("qty_per_box") is not None:
            self.set_number("qty_per_box", data["qty_per_box"])
        # Cost/Box: disabled pre-2026-09-09 (BUG-PROD-001), enabled + required since.
        if data.get("cost_per_box") is not None and not self.cost_per_box_disabled():
            self.set_number("cost_per_box", data["cost_per_box"])
        if data.get("retail_price_per_box") is not None:
            self.set_number("retail_price_per_box", data["retail_price_per_box"])
        if data.get("wholesale_price_per_box") is not None:
            self.set_number("wholesale_price_per_box", data["wholesale_price_per_box"])
        if "medicine" in data:
            self.toggle_medicine(bool(data["medicine"]))

        extra = {"rack_no", "barcode_value", "volume", "origin"} & set(data)
        if extra:
            self.expand_additional_info()
            if data.get("rack_no") is not None:
                self.set_number("rack_no", data["rack_no"])
            if data.get("barcode_value") is not None:
                self.set_text("barcode_value", data["barcode_value"])
            if data.get("volume") is not None:
                self.set_text("volume", data["volume"])
            if data.get("origin"):
                self.origin.select(data["origin"])

    def submit(self) -> None:
        self.click(self.drawer.button("Confirm New Product"), description="Confirm New Product")

    @allure.step("Create product")
    def create(self, data: dict[str, Any]) -> None:
        self.fill_form(data)
        self.submit()

    # ------------------------------------------------------------------ reads
    def validation_errors(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for item in self.drawer.root.locator(".ant-form-item").all():
            label = item.locator("label").first
            err = item.locator(".ant-form-item-explain-error, .ant-form-item-explain")
            if label.count() and err.count():
                out[label.inner_text().strip()] = err.first.inner_text().strip()
        return out

    def cost_per_box_disabled(self) -> bool:
        return self._field("cost_per_box").is_disabled()

    # visible label text per field id (AntD Select labels don't always carry a
    # matching for= attribute, so match on text)
    _LABEL_TEXT = {
        "product_name": "Product Name", "strength": "Strength",
        "product_type": "Product Type", "company": "Company Name",
        "generic": "Generic Name", "qty_per_box": "Qty/Box",
        "cost_per_box": "Cost/Box", "retail_price_per_box": "Retail Price/Box",
        "wholesale_price_per_box": "Wholesale Price/Box",
        "rack_no": "Rack No", "barcode_value": "Barcode Value",
        "volume": "Volume", "origin": "Country Of Origin",
    }

    def field_label(self, key: str) -> Locator:
        """The AntD <label> for a field, matched first by ``for=`` then by text."""
        by_for = self.drawer.root.locator(f"label[for='{F[key]}']")
        if by_for.count():
            return by_for.first
        txt = self._LABEL_TEXT.get(key, "")
        return self.drawer.root.locator(".ant-form-item label", has_text=txt).first

    def is_required_marked(self, key: str) -> bool:
        """Does the field's label show the required asterisk (AntD adds the
        ``ant-form-item-required`` class)?"""
        lbl = self.field_label(key)
        if not lbl.count():
            return False
        cls = lbl.get_attribute("class") or ""
        return "ant-form-item-required" in cls

    def number_raw(self, key: str) -> str:
        """Raw value a number field holds after a fill (to check client-side
        clamping / min guards - BUG-PROD-004)."""
        return self._field(key).input_value()

    def text_maxlength(self, key: str) -> int:
        v = self._field(key).get_attribute("maxlength")
        return int(v) if v is not None else -1

    def form_state(self) -> dict[str, str]:
        """Snapshot every visible input / select value in the drawer.  Used to
        prove BUG-PROD-005 (the drawer keeps its previous unsaved input when it
        is closed and reopened)."""
        out: dict[str, str] = {}
        for inp in self.drawer.root.locator("input").all():
            try:
                key = inp.get_attribute("placeholder") or inp.get_attribute("id") or inp.get_attribute("type") or "?"
                out[key] = inp.input_value()
            except Exception:
                continue
        for sel in self.drawer.root.locator(".ant-select").all():
            try:
                label = sel.locator("xpath=ancestor::*[contains(@class,'ant-form-item')][1]//label").first
                name = label.inner_text().strip() if label.count() else "select"
                val = sel.locator(".ant-select-selection-item, .ant-select-content-has-value")
                out[f"select:{name}"] = val.first.inner_text().strip() if val.count() else ""
            except Exception:
                continue
        return out

    def additional_info_expanded(self) -> bool:
        return self._field("rack_no").count() > 0 and self._field("rack_no").is_visible()

    def reopen(self, my_products) -> "AddProductPage":
        """Close (Cancel) then reopen the Add drawer via the page button."""
        self.close()
        return my_products.open_add_product()

    def x_close(self) -> None:
        """Close the drawer via its top-right X icon (not the Cancel button)."""
        x = self.drawer.root.locator(".ant-drawer-close, [aria-label='Close']").first
        self.click(x, description="drawer X icon")

    # ------------------------------------------------------------------ create + capture
    class FillError(RuntimeError):
        """Raised when the form could not be filled (usually an AntD Select that
        would not open/filter on a slow or degraded environment).  Tests should
        turn this into a ``pytest.skip`` rather than a misleading failure."""

    def create_and_capture(self, data: dict[str, Any], *, double_submit: bool = False) -> dict[str, Any]:
        """Fill ``data`` and Confirm.  Returns a dict:
            {status, body, inline (label->msg), toast[list], drawer_open, req_count}
        ``status``/``body`` are None if no create request was made (i.e. client
        validation blocked the submit).  ``req_count`` counts create POSTs seen
        (for the double-submit idempotency check).

        Raises ``AddProductPage.FillError`` if a required Select could not be set
        (environment/automation flake, not a product defect)."""
        try:
            self.fill_form(data)
        except Exception as exc:  # noqa: BLE001
            raise AddProductPage.FillError(str(exc)) from exc
        seen: list = []
        self.page.on("response", lambda r: seen.append(r) if "pharmacy-products/create/" in r.url else None)
        status = body = None
        try:
            with self.page.expect_response(
                lambda r: "pharmacy-products/create/" in r.url, timeout=8_000
            ) as ri:
                self.submit()
                if double_submit:
                    self.submit()
            resp = ri.value
            status = resp.status
            try:
                body = resp.json()
            except Exception:
                body = resp.text()
        except Exception:
            pass  # no request => client-side validation stopped it
        self.page.wait_for_timeout(800)
        return {
            "status": status,
            "body": body,
            "inline": self.validation_errors(),
            "toast": self.toast_messages(),
            "drawer_open": self.is_open(),
            "req_count": len(seen),
        }

    # ------------------------------------------------------------------ add company/generic
    # NOTE (BUG-PROD-002): as of 2026-09-08 the green [+] buttons beside Company
    # and Generic in this drawer do nothing (no modal, no network, no error).
    # These helpers are kept for when the feature is fixed; tests assert the
    # bug until then.
    def company_plus_button(self) -> Locator:
        return self.drawer.root.locator(
            ".ant-form-item:has(label:text-is('Company Name')) button.ant-btn-icon-only"
        ).first

    def generic_plus_button(self) -> Locator:
        return self.drawer.root.locator(
            ".ant-form-item:has(label:text-is('Generic Name')) button.ant-btn-icon-only"
        ).first

    def open_add_company(self) -> AddCompanyMiniForm:
        self.click(self.company_plus_button(), description="+ add company")
        return AddCompanyMiniForm(self.page, self.click).wait()

    def open_add_generic(self) -> AddCompanyMiniForm:
        self.click(self.generic_plus_button(), description="+ add generic")
        return AddCompanyMiniForm(self.page, self.click).wait()
