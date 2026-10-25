"""What the Inventory Config values do: the VAT Percentage drives TP/VAT mode (VAT/Box = TP x %), the Opening Stock Percentage
drives Opening Stock mode (BTP+VAT/Box = Retail x (1 - %)). Inventories created before a change keep their figures."""
from __future__ import annotations

import allure
import pytest

from pages.inventory_page import InventoryPage
from pages.inventory_record_page import InventoryRecordPage
from tests.inventory.config_module.conftest import DEFAULT_OPENING, DEFAULT_VAT, set_config
from tests.inventory.edit_module.helpers import num, record_row
from utils.inventory_calc import excel_round
from utils.opening_calc import btp_for
from utils.tpvat_calc import vat_for

ROUND = pytest.approx
CREDIT = dict(paid_ratio=0.0, choice="Due & Buy")      # the pharmacy has no Cash balance


def _tpvat_form(page, catalogue) -> InventoryPage:
    inv = InventoryPage(page)
    InventoryPage.product_catalogue = catalogue
    inv.open("TP/VAT")                                  # a full page load: the configuration is read again
    return inv


def _opening_form(page, catalogue) -> InventoryPage:
    inv = InventoryPage(page)
    InventoryPage.product_catalogue = catalogue
    inv.open("Opening Stock")
    return inv


@allure.epic("Inventory")
@allure.feature("Inventory Config - VAT Percentage in TP/VAT mode")
class TestVatPercentageEffect:
    @allure.story("The VAT/Box label and the pre-filled VAT/Box follow the configured percentage")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("vat", [0, 5, 10, 17.4, 25.5, 100], ids=lambda v: f"vat{v}")
    def test_label_and_preload(self, page, catalogue, restore, vat):
        set_config(page, vat=vat)
        inv = _tpvat_form(page, catalogue)
        for _ in range(20):                             # the label is redrawn once the configuration arrives
            labels = [t.strip().replace(" ", "") for t in page.locator("label").all_inner_texts()]
            if any(l.startswith("VAT/Box") and f"({vat:g}%)" in l for l in labels):
                break
            page.wait_for_timeout(500)
        assert any(l.startswith("VAT/Box") and f"({vat:g}%)" in l for l in labels), (vat, [l for l in labels if "VAT" in l])
        inv.select_product(inv.resolve_product("P0"), exact=True)
        tp, got = inv.form_number("tp_per_box"), inv.form_number("vat_per_box")
        assert got == ROUND(vat_for(tp, vat / 100), abs=0.011), (vat, tp, got)

    @allure.story("Typing TP/Box pre-fills VAT/Box = TP x the configured percentage")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("vat", [0, 5, 10, 33.3, 100], ids=lambda v: f"vat{v}")
    @pytest.mark.parametrize("tp", [0.01, 10, 89.44, 125.75, 999.99, 12345.67], ids=lambda v: f"tp{v}")
    def test_typed_tp(self, page, catalogue, restore, vat, tp):
        set_config(page, vat=vat)
        inv = _tpvat_form(page, catalogue)
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("tp_per_box", tp)
        inv.field("tp_per_box").blur()
        page.wait_for_timeout(300)
        assert inv.form_number("vat_per_box") == ROUND(vat_for(tp, vat / 100), abs=0.011), (vat, tp, inv.value_of("vat_per_box"))

    @allure.story("A manually typed VAT/Box still overrides the configured percentage")
    def test_manual_vat_overrides(self, page, catalogue, restore):
        set_config(page, vat=10)
        inv = _tpvat_form(page, catalogue)
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("tp_per_box", 100)
        inv.field("tp_per_box").blur()
        inv.set_value("vat_per_box", 3)
        inv.field("vat_per_box").blur()
        page.wait_for_timeout(300)
        assert inv.form_number("vat_per_box") == 3 and inv.form_number("tp_per_box") == 100

    @allure.story("A TP/VAT inventory created under a changed percentage is priced with it (cart, checkout, record)")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("vat", [0, 10, 100], ids=lambda v: f"vat{v}")
    def test_inventory_uses_configured_vat(self, page, create_in, restore, vat):
        set_config(page, vat=vat)
        saved = create_in("TP/VAT", "two_plain", **CREDIT)
        expected = float(excel_round(sum(
            s.box_qty * (s.tp_per_box + vat_for(s.tp_per_box, vat / 100)) for s in saved.journey.specs)))
        assert saved.final == ROUND(expected, abs=1.01), (vat, saved.final, expected)
        row = record_row(InventoryRecordPage(page), saved.inventory_id)
        assert num(row["bill"]) == ROUND(saved.final, abs=0.51), row

    @allure.story("Changing the percentage does not change an inventory created before (its bill and VAT stay)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_existing_inventory_unchanged(self, page, create_in, restore):
        saved = create_in("TP/VAT", "two_plain", **CREDIT)
        before = record_row(InventoryRecordPage(page), saved.inventory_id)
        set_config(page, vat=3)
        after = record_row(InventoryRecordPage(page), saved.inventory_id)
        assert after["bill"] == before["bill"], (before, after)

    @allure.story("The Opening Stock percentage is independent of the VAT percentage")
    def test_vat_change_leaves_opening_default(self, page, catalogue, restore):
        set_config(page, vat=40)
        inv = _opening_form(page, catalogue)
        assert float(inv.value_of("opening_stock_percent")) == DEFAULT_OPENING


@allure.epic("Inventory")
@allure.feature("Inventory Config - Opening Stock Percentage in Opening Stock mode")
class TestOpeningPercentageEffect:
    @allure.story("Opening Stock (%) opens with the configured value and BTP+VAT/Box = Retail x (1 - %)")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("pct", [0, 5, 12, 20, 33.33, 50, 99, 100], ids=lambda v: f"pct{v}")
    def test_default_and_btp(self, page, catalogue, restore, pct):
        set_config(page, opening=pct)
        inv = _opening_form(page, catalogue)
        inv.select_product(inv.resolve_product("P0"), exact=True)
        page.wait_for_timeout(600)
        assert float(inv.value_of("opening_stock_percent")) == ROUND(pct, abs=0.001)
        retail = inv.form_number("retail_price")
        assert inv.form_number("price_per_box") == ROUND(btp_for(retail, pct), abs=0.0051), (pct, retail)

    @allure.story("Selecting another product keeps the configured percentage")
    def test_other_product_keeps_default(self, page, catalogue, restore):
        set_config(page, opening=25)
        inv = _opening_form(page, catalogue)
        for ref in ("P0", "P1", "P2"):
            inv.select_product(inv.resolve_product(ref), exact=True)
            page.wait_for_timeout(500)
            assert float(inv.value_of("opening_stock_percent")) == 25, ref

    @allure.story("Editing Retail Price/Box re-derives BTP+VAT/Box at the configured percentage")
    @pytest.mark.parametrize("retail", [100, 33.33, 612, 999.99], ids=lambda v: f"retail{v}")
    def test_retail_edit_uses_config(self, page, catalogue, restore, retail):
        set_config(page, opening=20)
        inv = _opening_form(page, catalogue)
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("retail_price", retail)
        inv.field("retail_price").blur()
        page.wait_for_timeout(400)
        assert inv.form_number("price_per_box") == ROUND(btp_for(retail, 20), abs=0.0051)

    @allure.story("Typing another percentage in the form still overrides the configured one, and a new product returns to it")
    def test_form_override_then_reset(self, page, catalogue, restore):
        set_config(page, opening=20)
        inv = _opening_form(page, catalogue)
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("opening_stock_percent", 35)
        inv.field("opening_stock_percent").blur()
        page.wait_for_timeout(300)
        retail = inv.form_number("retail_price")
        assert inv.form_number("price_per_box") == ROUND(btp_for(retail, 35), abs=0.0051)
        inv.select_product(inv.resolve_product("P1"), exact=True)
        page.wait_for_timeout(500)
        assert float(inv.value_of("opening_stock_percent")) == 20

    @allure.story("An Opening Stock inventory created under a changed percentage is priced with it")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("pct", [0, 20, 50], ids=lambda v: f"pct{v}")
    def test_inventory_uses_configured_percentage(self, page, create_in, restore, pct):
        set_config(page, opening=pct)
        saved = create_in("Opening Stock", "single_plain", **CREDIT)
        line = saved.journey.lines[0]
        assert line.btp_vat_per_box == ROUND(btp_for(line.retail_per_box, pct), abs=0.0051), (pct, line)
        expected = float(excel_round(line.box_qty * btp_for(line.retail_per_box, pct)))
        assert saved.final == ROUND(expected, abs=1.01), (pct, saved.final, expected)

    @allure.story("Changing the percentage does not change an Opening Stock inventory created before")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_existing_inventory_unchanged(self, page, create_in, restore):
        saved = create_in("Opening Stock", "single_plain", **CREDIT)
        before = record_row(InventoryRecordPage(page), saved.inventory_id)
        set_config(page, opening=45)
        after = record_row(InventoryRecordPage(page), saved.inventory_id)
        assert after["bill"] == before["bill"], (before, after)

    @allure.story("The VAT percentage is independent of the Opening Stock percentage")
    def test_opening_change_leaves_vat_default(self, page, catalogue, restore):
        set_config(page, opening=45)
        inv = _tpvat_form(page, catalogue)
        inv.select_product(inv.resolve_product("P0"), exact=True)
        tp = inv.form_number("tp_per_box")
        assert inv.form_number("vat_per_box") == ROUND(vat_for(tp, DEFAULT_VAT / 100), abs=0.011)
