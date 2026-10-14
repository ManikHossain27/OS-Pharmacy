"""AntD confirm/Popconfirm modal wrapper (used by delete flows)."""
from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


class ConfirmModal:
    def __init__(self, page: Page):
        self.page = page

    @property
    def root(self) -> Locator:
        return self.page.locator(
            ".ant-modal-confirm, .ant-popover-content:has(.ant-popconfirm), .ant-modal-content"
        ).last

    def wait(self, timeout: int = 5_000) -> "ConfirmModal":
        expect(self.root).to_be_visible(timeout=timeout)
        return self

    def body_text(self) -> str:
        return self.root.inner_text().strip()

    def confirm(self, clicker, name: str = "OK") -> None:
        btn = self.root.get_by_role("button", name=name)
        if not btn.count():
            btn = self.root.get_by_role("button", name="Yes")
        clicker(btn, description="confirm modal OK")

    def cancel(self, clicker, name: str = "Cancel") -> None:
        btn = self.root.get_by_role("button", name=name)
        if not btn.count():
            btn = self.root.get_by_role("button", name="No")
        clicker(btn, description="confirm modal Cancel")
