"""Pharmacy / clinic picker (route: /pharmacies).

Cards are ``div.pharmacy-card[role=button]`` with an onclick handler.  Selecting
navigates to /dashboard for that pharmacy.  The sidebar then shows the active
pharmacy name above a "Change Pharmacy" button.
"""
from __future__ import annotations

import allure
from playwright.sync_api import expect

from config import settings
from pages.base_page import BasePage
from utils.constants import ROUTES


class PharmacySelectionPage(BasePage):
    route = ROUTES["pharmacies"]

    def __init__(self, page):
        super().__init__(page)
        self.cards = page.locator(".pharmacy-card")
        self.add_new_card = page.get_by_role("button", name="Add new pharmacy or clinic")
        self.search_input = page.get_by_placeholder("Search")  # present only if list is long

    # ------------------------------------------------------------------
    def card_for(self, name: str):
        card = self.cards.filter(has_text=name).first
        if card.count():
            return card
        # this build renders each pharmacy as a <button> (no .pharmacy-card class)
        return self.page.get_by_role("button", name=name).first

    def has_pharmacy(self, name: str, timeout: int = 10_000) -> bool:
        """Is a pharmacy card with this name present in the picker?  ``False``
        when the list is degraded (BUG-API-001 truncates it)."""
        try:
            self.page.get_by_role("button").filter(has_text=name).first.wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return self.cards.filter(has_text=name).count() > 0

    def names(self) -> list[str]:
        return [c.locator(".pharmacy-card-identity span, .ant-typography").first.inner_text().strip()
                for c in self.cards.all()]

    @allure.step("Select pharmacy: {name}")
    def select(self, name: str | None = None) -> None:
        name = name or settings.pharmacy_name
        if self.search_input.count():
            self.search_input.fill(name)

        card = self.card_for(name)
        # auto-waits for the (possibly search-filtered) card to render
        expect(card).to_be_visible(timeout=10_000)
        self.click(
            card,
            expect_effect=lambda: "/pharmacies" not in self.page.url,
            description=f"pharmacy card {name!r}",
        )
        self.page.wait_for_url(lambda u: "/pharmacies" not in u, timeout=settings.nav_timeout)
        self.wait_for_app_ready()

    def assert_selected(self, name: str | None = None) -> None:
        name = name or settings.pharmacy_name
        sidebar = self.page.locator("aside")
        expect(sidebar.get_by_text(name, exact=True).first).to_be_visible(timeout=10_000)
        expect(sidebar.get_by_text("Change Pharmacy")).to_be_visible()
