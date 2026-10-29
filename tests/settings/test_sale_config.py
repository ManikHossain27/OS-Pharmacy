"""Settings > Sale Config: persistence, Cancel, double-click Save. Every test puts the pharmacy's switches back (sale_config)."""
from __future__ import annotations

import allure
import pytest

pytestmark = [pytest.mark.sale, pytest.mark.regression]


@allure.epic("Sale")
@allure.feature("Sale Config")
class TestSaleConfig:

    @allure.story("TC-SALE-SC-02: a saved toggle persists after reload and leaves the others unchanged")
    def test_saved_toggles_persist(self, sale_config):
        before = sale_config.state()
        wanted = {"stockQty": not before["stockQty"], "rackNo": not before["rackNo"]}
        persisted = sale_config.apply(wanted)
        for name, value in wanted.items():
            assert persisted[name] is value, f"{name} should persist as {value}: {persisted}"
        untouched = {k: v for k, v in before.items() if k not in wanted}
        assert {k: persisted[k] for k in untouched} == untouched, "a switch the test did not touch changed"

    @allure.story("TC-SALE-SC-03: Cancel discards unsaved changes and sends no request")
    def test_cancel_discards_changes(self, sale_config):
        before = sale_config.state()
        puts: list[str] = []
        sale_config.page.on("request", lambda r: puts.append(r.url) if r.method == "PUT" and "sales-configs" in r.url else None)
        sale_config.toggle("stockQty")
        sale_config.cancel_btn.click()
        sale_config.page.wait_for_timeout(2_000)
        assert sale_config.state() == before
        assert not puts, f"Cancel must not save: {puts}"

    @allure.story("BUG-SALE-031: double-clicking Save Changes must send one update")
    @allure.issue("BUG-SALE-031")
    def test_double_click_save_sends_one_request(self, sale_config):
        sale_config.toggle("stockQty")
        statuses = sale_config.double_click_save()
        assert len(statuses) == 1, f"{len(statuses)} PUT requests for one logical save: {statuses}"
