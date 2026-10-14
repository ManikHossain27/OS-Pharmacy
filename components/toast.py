"""Toast / notification reader."""
from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

_SEL = ".ant-message-notice, .ant-notification-notice, [role='alert']"


class Toast:
    def __init__(self, page: Page):
        self.page = page

    @property
    def _loc(self) -> Locator:
        return self.page.locator(_SEL)

    def wait(self, contains: str = "", timeout: int = 8_000) -> str:
        self._loc.first.wait_for(state="visible", timeout=timeout)
        if contains:
            expect(self._loc.filter(has_text=contains).first).to_be_visible(timeout=timeout)
        return self._loc.first.inner_text().strip()

    def messages(self) -> list[str]:
        return [t.strip() for t in self._loc.all_inner_texts() if t.strip()]

    def success(self, contains: str = "", timeout: int = 8_000) -> str:
        loc = self.page.locator(
            ".ant-message-success, .ant-notification-notice-success, "
            ".ant-message-notice:has(.anticon-check-circle)"
        )
        loc.first.wait_for(state="visible", timeout=timeout)
        text = loc.first.inner_text().strip()
        assert not contains or contains.lower() in text.lower(), (
            f"success toast {text!r} does not contain {contains!r}"
        )
        return text
