"""Give a fresh pharmacy opening Cash so paid purchases do not fail with "Payment method 'CASH' has insufficient balance":
Accounting > Income > Add New Income (category "QA Opening Cash", payment method CASH).

Usage:  python tools/fund_return_pharmacy.py 5000000 "QA Ret Pharma A" "QA Ret Pharma B"
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright  # noqa: E402

from config import settings  # noqa: E402
from pages.pharmacy_selection_page import PharmacySelectionPage  # noqa: E402
from utils import auth  # noqa: E402

OPTION = ".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option"


def fund(pg, amount: str) -> None:
    pg.goto(settings.base_url + "income", wait_until="domcontentloaded")
    pg.get_by_role("button", name="Add New Income").click()
    pg.locator("#category").click(force=True)
    pg.wait_for_timeout(1500)
    options = [o.inner_text() for o in pg.locator(OPTION).all()]
    print("  categories:", options, flush=True)
    if options:
        pg.locator(OPTION).first.click()
    pg.locator("#amount").fill(amount)
    pg.locator("#paymentMethod").click(force=True)
    pg.locator(OPTION).filter(has_text="CASH").first.click()
    pg.locator("#note").fill("QA opening cash for Inventory Return tests " + time.strftime("%H:%M"))
    with pg.expect_response(lambda r: r.request.method == "POST" and "income" in r.url.lower(), timeout=30_000) as info:
        pg.get_by_role("button", name="Confirm New Income").click()
    print("  income", amount, "->", info.value.status, info.value.text()[:200], flush=True)


def main(amount: str, names: list[str]) -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False)
        ctx = b.new_context(base_url=settings.base_url, storage_state=str(settings.auth_state_path),
                            viewport={"width": 1700, "height": 1000})
        ctx.set_default_navigation_timeout(300_000)
        ctx.set_default_timeout(60_000)
        pg = ctx.new_page()
        for name in names:
            print(name, flush=True)
            pg.goto(settings.base_url + "pharmacies", wait_until="domcontentloaded")
            auth.ensure_logged_in(pg)
            pg.goto(settings.base_url + "pharmacies", wait_until="domcontentloaded")
            PharmacySelectionPage(pg).select(name)
            fund(pg, amount)
        b.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
