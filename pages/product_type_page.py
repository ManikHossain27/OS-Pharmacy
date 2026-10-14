"""Customizations -> Product Type List  (/product-types).

Confirmed live 2026-09-08: the Add form has ONLY a "Product Type Name" field
(id ``name``).  There is **no** Sort Order / Sequence / Priority field - but the
backend create still requires ``sortOrder`` (int) AND ``slug``, so creation is
broken via the UI and dumps raw errors into a toast
(``Invalid value for field 'sortOrder': expected a value of type int.`` then
``Product type slug must not be blank``) - see BUG-PTYPE-001.
"""
from __future__ import annotations

from pages.customization_list_page import CustomizationListPage, CustomizationEntityForm
from utils.constants import ROUTES

# Kept for a future build that adds an ordering field.
SORT_ORDER_LABELS = ("Sort Order", "Sequence", "Priority", "Serial", "Order")


class ProductTypePage(CustomizationListPage):
    route = ROUTES["product_type_list"]
    entity = "Product Type"
    add_button_name = "Add New Product Type"
    name_label = "Product Type Name"       # input id: name

    def open_add(self) -> CustomizationEntityForm:
        form = super().open_add()
        form.sort_order_label = self._detect_sort_order_label(form)
        return form

    @staticmethod
    def _detect_sort_order_label(form: CustomizationEntityForm) -> str | None:
        for label in SORT_ORDER_LABELS:
            if form.root.get_by_label(label).count():
                return label
        return None

    def has_sort_order_field(self) -> bool:
        form = self.open_add()
        present = form.sort_order_label is not None
        form.cancel()
        return present

    def create_with_sort_order(self, name: str, sort_order) -> list[str] | str:
        """Attempt create; if there is no Sort Order field this exercises
        BUG-PTYPE-001 (backend rejects the missing sortOrder/slug)."""
        form = self.open_add()
        form.set_name(name)
        if form.sort_order_label:
            form.set_field(form.sort_order_label, sort_order)
        form.save()
        # Wait for either a success toast or an error (inline / toast) to appear.
        feedback = self.page.locator(
            ".ant-form-item-explain-error, .ant-message-notice, .ant-notification-notice, [role='alert']"
        )
        try:
            feedback.first.wait_for(state="visible", timeout=8_000)
        except Exception:
            pass
        errs = form.errors() + self.toast.messages()
        return errs if any(errs) else self.toast.wait(timeout=8_000)

    def first_editable_type(self) -> str | None:
        """Name of the first row that carries an Edit pencil (a pharmacy-created,
        global:false type).  ``None`` if the visible page has only global rows,
        or the list is empty / not loaded."""
        try:
            n = min(self.table.row_count(), 50)
        except Exception:
            return None
        for i in range(n):
            try:
                name = self.table.cell(i, "Product Type")
            except Exception:
                continue
            if name and name.lower() not in ("no product type found", "no data") and self.can_edit(name):
                return name
        return None
