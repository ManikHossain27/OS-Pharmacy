"""Settings > Inventory Config: the VAT Percentage and Opening Stock Percentage fields - defaults, saving, persistence,
Cancel, validation, precision, per-pharmacy scope."""
from __future__ import annotations

import allure
import pytest

from config import settings
from pages.inventory_config_page import InventoryConfigPage
from pages.pharmacy_selection_page import PharmacySelectionPage
from tests.inventory.config_module.conftest import DEFAULT_OPENING, DEFAULT_VAT

ROUND = pytest.approx


def _reload(page) -> InventoryConfigPage:
    return InventoryConfigPage(page).open()


@allure.epic("Inventory")
@allure.feature("Inventory Config - page")
class TestConfigPage:
    @allure.story("The page opens with the system defaults: VAT 17.4 %, Opening Stock 12 %")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_defaults(self, cfg):
        assert cfg.numbers() == (DEFAULT_VAT, DEFAULT_OPENING), cfg.values()

    @allure.story("Both fields are required and the page offers Cancel and Save Changes")
    def test_layout(self, cfg):
        required = cfg.required_labels()
        assert any("VAT Percentage" in t for t in required) and any("Opening Stock Percentage" in t for t in required), required
        assert cfg.save_btn.is_visible() and cfg.cancel_btn.is_visible()

    @allure.story("A saved VAT percentage persists after reload; the Opening Stock percentage is untouched")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("vat", [0, 0.01, 5, 10, 17.4, 25.5, 50, 99.99, 100], ids=lambda v: f"vat{v}")
    def test_save_vat(self, page, cfg, vat):
        status, body, toast = cfg.save_values(vat=vat)
        assert status is not None and status < 300, (status, body[:200], toast)
        assert _reload(page).numbers() == (ROUND(vat, abs=1e-6), DEFAULT_OPENING)

    @allure.story("A saved Opening Stock percentage persists after reload; the VAT percentage is untouched")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.parametrize("pct", [0, 0.5, 5, 12, 20, 33.33, 50, 99.99, 100], ids=lambda v: f"open{v}")
    def test_save_opening(self, page, cfg, pct):
        status, body, toast = cfg.save_values(opening=pct)
        assert status is not None and status < 300, (status, body[:200], toast)
        assert _reload(page).numbers() == (DEFAULT_VAT, ROUND(pct, abs=1e-6))

    @allure.story("Both fields can be changed and saved together")
    def test_save_both(self, page, cfg):
        status, body, _ = cfg.save_values(vat=8.5, opening=22.5)
        assert status is not None and status < 300, (status, body[:200])
        assert _reload(page).numbers() == (ROUND(8.5), ROUND(22.5))

    @allure.story("A successful save tells the user (toast / message)")
    def test_save_feedback(self, cfg):
        status, body, toast = cfg.save_values(vat=11)
        assert status is not None and status < 300 and toast, f"no confirmation shown: {status} {toast!r}"

    @allure.story("Cancel discards unsaved edits")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cancel_discards(self, page, cfg):
        cfg.set_vat(3)
        cfg.set_opening(40)
        cfg.cancel()
        assert _reload(page).numbers() == (DEFAULT_VAT, DEFAULT_OPENING)

    @allure.story("Edits that are not saved are lost when the page is reloaded")
    def test_unsaved_edit_lost_on_reload(self, page, cfg):
        cfg.set_vat(4)
        assert _reload(page).numbers() == (DEFAULT_VAT, DEFAULT_OPENING)

    @allure.story("Saving without changing anything keeps the values")
    def test_save_unchanged(self, page, cfg):
        status, body, _ = cfg.save()
        assert status is None or status < 300, (status, body[:200])
        assert _reload(page).numbers() == (DEFAULT_VAT, DEFAULT_OPENING)

    @allure.story("Whitespace and leading zeros are tidied: ' 12 ' -> 12, '007' -> 7")
    @pytest.mark.parametrize("typed,expected", [(" 12 ", 12), ("007", 7), ("5.50", 5.5)], ids=["spaces", "zeros", "trailing-zero"])
    def test_tidy_input(self, page, cfg, typed, expected):
        status, body, _ = cfg.save_values(vat=typed)
        assert status is not None and status < 300, (status, body[:200])
        assert _reload(page).numbers()[0] == ROUND(expected, abs=1e-6)

    @allure.story("More than two decimals: the value is rounded or kept, never mangled")
    def test_many_decimals(self, page, cfg):
        status, body, _ = cfg.save_values(vat="17.456")
        assert status is not None and status < 300, (status, body[:200])
        assert _reload(page).numbers()[0] == ROUND(17.456, abs=0.006)

    @allure.story("A double-click on Save Changes saves once and leaves the right value")
    @allure.severity(allure.severity_level.NORMAL)
    def test_double_click_save(self, page, cfg):
        writes: list[int] = []
        page.on("response", lambda r: writes.append(r.status) if r.request.method in ("POST", "PUT", "PATCH") and "/secured/" in r.url else None)
        cfg.set_vat(9)
        cfg.save_btn.dblclick()
        page.wait_for_timeout(6000)
        assert all(s < 300 for s in writes), writes
        assert len(writes) <= 1, f"{len(writes)} save requests for one double-click"
        assert _reload(page).numbers()[0] == ROUND(9)


INVALID = {
    "blank": "", "negative": "-1", "tiny-negative": "-0.01", "just-over-100": "100.01", "101": "101", "1000": "1000",
    "text": "abc", "exponent": "1e2", "double-dash": "--5", "two-dots": "5..5", "percent-sign": "%", "huge": "99999999999999999999",
}


@allure.epic("Inventory")
@allure.feature("Inventory Config - validation")
class TestConfigValidation:
    @allure.story("An invalid VAT percentage is never stored: the saved value stays a valid 0-100 number")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.parametrize("kind", list(INVALID))
    def test_invalid_vat(self, page, cfg, kind):
        cfg.set_vat(INVALID[kind])
        shown = cfg.values()[0]
        status, body = (None, "")
        if cfg.save_enabled():
            status, body, _ = cfg.save()
        stored = _reload(page).numbers()[0]
        assert 0 <= stored <= 100, f"typed {INVALID[kind]!r} (shown {shown!r}, HTTP {status}) -> stored {stored}"
        if kind in ("negative", "tiny-negative", "just-over-100", "101", "1000", "huge"):
            assert stored != ROUND(float(INVALID[kind]), abs=1e-6), f"the invalid value {INVALID[kind]!r} was stored as {stored}"

    @allure.story("An invalid Opening Stock percentage is never stored: the saved value stays a valid 0-100 number")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.parametrize("kind", list(INVALID))
    def test_invalid_opening(self, page, cfg, kind):
        cfg.set_opening(INVALID[kind])
        shown = cfg.values()[1]
        status = None
        if cfg.save_enabled():
            status, _, _ = cfg.save()
        stored = _reload(page).numbers()[1]
        assert 0 <= stored <= 100, f"typed {INVALID[kind]!r} (shown {shown!r}, HTTP {status}) -> stored {stored}"
        if kind in ("negative", "tiny-negative", "just-over-100", "101", "1000", "huge"):
            assert stored != ROUND(float(INVALID[kind]), abs=1e-6), f"the invalid value {INVALID[kind]!r} was stored as {stored}"

    @allure.story("Saving with a field left blank is refused (both fields are required)")
    @pytest.mark.negative
    @pytest.mark.parametrize("field", ["vat", "opening"])
    def test_blank_refused(self, page, cfg, field):
        (cfg.set_vat if field == "vat" else cfg.set_opening)("")
        status = None
        if cfg.save_enabled():
            status, _, _ = cfg.save()
        assert status is None or status >= 400, f"a blank {field} was saved (HTTP {status})"
        assert _reload(page).numbers() == (DEFAULT_VAT, DEFAULT_OPENING)


@allure.epic("Inventory")
@allure.feature("Inventory Config - scope")
class TestConfigScope:
    @allure.story("The configuration belongs to one pharmacy: another pharmacy keeps its own values")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_other_pharmacy_unaffected(self, page, cfg):
        status, body, _ = cfg.save_values(vat=6, opening=30)
        assert status is not None and status < 300, (status, body[:200])
        mine = settings.pharmacy_name
        other = "Manik Pharma"                     # not used by the parallel Inventory Config shards
        try:
            page.goto(settings.base_url + "pharmacies", wait_until="domcontentloaded")
            PharmacySelectionPage(page).select(other)
            assert InventoryConfigPage(page).open().numbers() == (DEFAULT_VAT, DEFAULT_OPENING), \
                "another pharmacy shows this pharmacy's configuration"
        finally:
            page.goto(settings.base_url + "pharmacies", wait_until="domcontentloaded")
            PharmacySelectionPage(page).select(mine)
