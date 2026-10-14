"""AntD right-hand side Drawer (used by Add New Product, add company/generic)."""
from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


class SideDrawer:
    def __init__(self, page: Page, title: str | None = None):
        self.page = page
        self.title = title

    @property
    def root(self) -> Locator:
        loc = self.page.locator(".ant-drawer-open [role='dialog'], .ant-drawer [role='dialog']")
        if self.title:
            return loc.filter(has_text=self.title).first
        return loc.first

    def is_open(self) -> bool:
        return self.page.locator(".ant-drawer-open").count() > 0 and self.root.count() > 0

    def wait_open(self, timeout: int = 8_000) -> "SideDrawer":
        expect(self.page.locator(".ant-drawer-open")).to_be_visible(timeout=timeout)
        return self

    def wait_closed(self, timeout: int = 8_000) -> None:
        expect(self.page.locator(".ant-drawer-open")).to_have_count(0, timeout=timeout)

    def field(self, field_id: str) -> Locator:
        return self.root.locator(f"#{field_id}")

    def button(self, name: str) -> Locator:
        return self.root.get_by_role("button", name=name)

    def close_x(self, clicker) -> None:
        clicker(self.root.locator(".ant-drawer-close, [aria-label='Close']").first,
                expect_effect=lambda: not self.is_open(), description="drawer X")

    def cancel(self, clicker) -> None:
        clicker(self.button("Cancel"), expect_effect=lambda: not self.is_open(),
                description="drawer Cancel")
