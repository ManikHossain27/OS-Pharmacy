"""Shared behaviour for the Customization list screens.

Company List, Generic List and Product Type List are the same shape: a searchable
/ sortable / paginated table plus an Add / Edit modal (drawer) and (where
available) a delete confirm.  The concrete pages set ``route``, ``entity`` and the
Add-button / name-field labels.
"""
from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator, Page, expect

from components.confirm_modal import ConfirmModal
from components.data_table import DataTable
from components.pagination import Pagination
from components.search_field import SearchField
from components.toast import Toast
from pages.base_page import BasePage
from utils.constants import CUSTOMIZATION_EDIT_ICON


class CustomizationEntityForm:
    """Add / Edit form for a customization entity (modal or drawer)."""

    def __init__(self, page: Page, clicker, name_label: str):
        self.page = page
        self._click = clicker
        self.name_label = name_label
        self.root = page.locator(".ant-modal-content, .ant-drawer-open [role='dialog']").last

    def wait(self) -> "CustomizationEntityForm":
        expect(self.root).to_be_visible(timeout=6_000)
        return self

    def name_field(self) -> Locator:
        by_label = self.root.get_by_label(self.name_label)
        return by_label if by_label.count() else self.root.get_by_role("textbox").first

    def field(self, label: str) -> Locator:
        loc = self.root.get_by_label(label)
        return loc if loc.count() else self.root.locator(f"#{label}")

    def set_name(self, value: str) -> None:
        f = self.name_field()
        f.fill("")
        f.fill(value)

    def set_field(self, label: str, value) -> None:
        f = self.field(label)
        f.fill("")
        f.fill(str(value))

    def save(self) -> None:
        btn = self.root.get_by_role("button", name=re.compile("save|add|confirm|update|create", re.I)).last
        self._click(btn, description="save entity")

    def cancel(self) -> None:
        self._click(self.root.get_by_role("button", name="Cancel"), description="cancel entity")

    def errors(self) -> list[str]:
        return [t.strip() for t in self.root.locator(
            ".ant-form-item-explain-error, .ant-form-item-explain").all_inner_texts() if t.strip()]


class CustomizationListPage(BasePage):
    entity: str = "Entity"
    add_button_name: str = "Add"
    name_label: str = "Name"

    def __init__(self, page: Page):
        super().__init__(page)
        self.table = DataTable(page)
        self.pagination = Pagination(page)
        self.toast = Toast(page)
        self.confirm = ConfirmModal(page)
        self.add_btn = page.get_by_role("button", name=re.compile(self.add_button_name, re.I))
        search_loc = page.get_by_placeholder(re.compile("search", re.I)).first
        self.search_field = SearchField(page, search_loc)

    # ------------------------------------------------------------------
    def wait_loaded(self) -> "CustomizationListPage":
        expect(self.page.locator("table").first).to_be_visible()
        return self

    def open_add(self) -> CustomizationEntityForm:
        form = CustomizationEntityForm(self.page, self.click, self.name_label)
        self.click(self.add_btn, expect_effect=lambda: form.root.count() > 0,
                   description=f"Add {self.entity}")
        return form.wait()

    @allure.step("Create {self.entity}: {name}")
    def create(self, name: str, **extra) -> str:
        form = self.open_add()
        form.set_name(name)
        for k, v in extra.items():
            form.set_field(k, v)
        form.save()
        return self.toast.wait(timeout=8_000)

    def create_expecting_error(self, name: str, **extra) -> list[str]:
        form = self.open_add()
        form.set_name(name)
        for k, v in extra.items():
            form.set_field(k, v)
        form.save()
        # Wait until the failure surfaces (inline error or error toast) rather
        # than sleeping a fixed amount.
        feedback = self.page.locator(
            ".ant-form-item-explain-error, .ant-message-notice, .ant-notification-notice, [role='alert']"
        )
        try:
            feedback.first.wait_for(state="visible", timeout=8_000)
        except Exception:
            pass
        return form.errors() + self.toast.messages()

    # ------------------------------------------------------------------ reads
    def search(self, term: str) -> None:
        self.search_field.search(term)

    def has_entity(self, name: str) -> bool:
        return self.table.has_row(name)

    def row(self, name: str) -> Locator:
        return self.table.row_by_text(name)

    def edit_icon(self, name: str) -> Locator:
        """The per-row Edit control - an icon-only clickable <div> (no accessible
        name).  Only present on rows this pharmacy created (global:false)."""
        row = self.row(name)
        by_role = row.get_by_role("button", name=re.compile("edit", re.I))
        if by_role.count():
            return by_role.first
        return row.locator(CUSTOMIZATION_EDIT_ICON).first

    def can_edit(self, name: str) -> bool:
        return self.edit_icon(name).count() > 0

    def edit(self, name: str) -> CustomizationEntityForm:
        self.click(self.edit_icon(name), description=f"edit {name}")
        return CustomizationEntityForm(self.page, self.click, self.name_label).wait()

    def edit_expecting_error(self, name: str, new_name: str, **extra) -> list[str]:
        """Rename ``name`` -> ``new_name`` and return whatever feedback surfaces
        (inline errors + toast).  Used to prove BUG-PTYPE-002 (edit leaks the raw
        ``sortOrder ... expected a value of type int`` backend error)."""
        form = self.edit(name)
        form.set_name(new_name)
        for k, v in extra.items():
            form.set_field(k, v)
        form.save()
        feedback = self.page.locator(
            ".ant-form-item-explain-error, .ant-message-notice, .ant-notification-notice, [role='alert']"
        )
        try:
            feedback.first.wait_for(state="visible", timeout=8_000)
        except Exception:
            pass
        return form.errors() + self.toast.messages()

    def delete(self, name: str) -> str:
        self.click(self.row(name).get_by_role("button", name=re.compile("delete|remove", re.I)),
                   description=f"delete {name}")
        self.confirm.wait().confirm(self.click)
        return self.toast.wait(timeout=8_000)

    def can_delete(self, name: str) -> bool:
        return self.row(name).get_by_role("button", name=re.compile("delete|remove", re.I)).count() > 0
