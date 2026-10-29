"""Settings pages (Settings menu): Sale Config, Loyalty Config. Other settings pages (Inventory Config, Invoice Config, ...) can be
added here; ``pages/inventory_config_page.py`` is still at its old path because the Inventory suites import it from there."""
from pages.settings.loyalty_config_page import LoyaltyConfigPage
from pages.settings.sale_config_page import SaleConfigPage

__all__ = ["LoyaltyConfigPage", "SaleConfigPage"]
