"""Settings > Loyalty Config (TC-SALE-LC-01..06). The four numbers are per pharmacy; ``loyalty_config`` puts the stored values back
after every test, so a failing test does not leave the loyalty program changed.

Saving valid values here does not send any SMS (the OTP is only sent when points are redeemed at checkout).
"""
from __future__ import annotations

import allure
import pytest

pytestmark = [pytest.mark.sale, pytest.mark.regression]

VALID = dict(earning=100, redemption=10, min_redeem=50, max_redeem=500)


@allure.epic("Sale")
@allure.feature("Loyalty Config")
class TestLoyaltyConfig:

    @allure.story("TC-SALE-LC-01: the page shows the four rules and their stored values")
    def test_page_shows_four_rules(self, loyalty_config):
        text = loyalty_config.labels()
        for label in ("Earning Rule", "Redemption Rule", "Minimum Redeem Points", "Max Redeem Limit per Transaction"):
            assert label in text, f"{label!r} missing from the page"
        assert all(v != "" for v in loyalty_config.values().values()), "a rule has no stored value"

    @allure.story("TC-SALE-LC-02: valid values are saved and still there after a reload")
    def test_valid_values_persist(self, loyalty_config):
        loyalty_config.set(**VALID)
        status, body, text = loyalty_config.save()
        assert status is not None and status < 300, f"save failed: {status} {text}"
        assert loyalty_config.open().values() == {k: str(v) for k, v in VALID.items()}

    @allure.story("TC-SALE-LC-04: text is not accepted as a rule value")
    def test_text_is_not_saved(self, loyalty_config):
        before = loyalty_config.values()
        loyalty_config.set(earning="abc")
        status, _, text = loyalty_config.save()
        assert status is None, f"text was sent to the server (status {status})"
        assert text, "no validation message for text in Earning Rule"
        assert loyalty_config.open().values() == before

    @allure.story("BUG-SALE-025: negative numbers are rejected, not silently saved as 0")
    @allure.issue("BUG-SALE-025")
    def test_negative_numbers_are_rejected(self, loyalty_config):
        # the stored values must be non-zero first, or "saved as 0" cannot be told from "unchanged"
        loyalty_config.set(**VALID)
        status, _, text = loyalty_config.save()
        assert status is not None and status < 300, f"set-up save failed: {status} {text}"
        before = loyalty_config.open().values()
        assert before == {k: str(v) for k, v in VALID.items()}
        loyalty_config.set(earning=-5, redemption=-1)
        status, body, text = loyalty_config.save()
        saved = loyalty_config.open().values()
        assert saved == before, (
            f"-5 / -1 changed the stored rules to {saved} (request {body[:120]!r}, message {text!r}) - "
            "the loyalty program was switched off by an invalid entry")

    @allure.story("TC-SALE-LC-05: Minimum redeem above Maximum is rejected by the server with a clear message")
    def test_minimum_above_maximum_is_rejected(self, loyalty_config):
        before = loyalty_config.values()
        loyalty_config.set(min_redeem=600, max_redeem=500)
        status, _, text = loyalty_config.save()
        assert status is not None and status >= 400, f"min 600 > max 500 was accepted: {status} {text}"
        assert "greater than" in text.lower(), f"unclear message: {text!r}"
        assert loyalty_config.open().values() == before

    @allure.story("TC-SALE-LC-06: Cancel discards edits")
    def test_cancel_discards_edits(self, loyalty_config):
        before = loyalty_config.values()
        loyalty_config.set(earning=7)
        loyalty_config.cancel_btn.click()
        loyalty_config.page.wait_for_timeout(2_000)
        assert loyalty_config.values() == before
