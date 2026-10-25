"""Prepare a fresh pharmacy for the Inventory Return suite: import three catalogue products and add two suppliers.

Usage:  python tools/setup_return_pharmacy.py "QA Ret Pharma A" "QA Ret Pharma B"
(The pharmacy must already exist - add it on /pharmacies with "Add new pharmacy or clinic".)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright  # noqa: E402

from config import settings  # noqa: E402
from pages.login_page import LoginPage  # noqa: E402
from pages.pharmacy_selection_page import PharmacySelectionPage  # noqa: E402
from pages.product_catalog_page import ProductCatalogPage  # noqa: E402

PRODUCTS = [("100", "100%"), ("3 BION", "3 BION"), ("3BIOTIC 100GM", "3BIOTIC 100GM")]
SUPPLIERS = [("QA Edit Supplier", "1711223344"), ("QA Edit Supplier B", "1711223355")]


def import_products(pg) -> None:
    cat = ProductCatalogPage(pg)
    cat.open()
    for term, name in PRODUCTS:
        cat.search(term)
        pg.wait_for_timeout(4000)
        row = cat.row(name)
        if row.count() and not cat.is_already_imported(name):
            print("  import", name, cat.import_row(name), flush=True)
        else:
            print("  already imported / not found:", name, flush=True)


def add_suppliers(pg) -> None:
    pg.goto(settings.base_url + "supplier", wait_until="domcontentloaded")
    pg.get_by_role("button", name="Add New Supplier").wait_for(timeout=120_000)
    pg.wait_for_timeout(3000)
    for name, phone in SUPPLIERS:
        if pg.locator("tbody tr.ant-table-row").filter(has_text=name).count():
            print("  supplier exists", name, flush=True)
            continue
        pg.get_by_role("button", name="Add New Supplier").click()
        pg.locator("#supplierName").fill(name)
        pg.locator("#phoneNumber").fill(phone)
        with pg.expect_response(lambda r: r.request.method == "POST" and "supplier" in r.url, timeout=30_000) as info:
            pg.get_by_role("button", name="Confirm New Supplier").click()
        print("  supplier", name, info.value.status, flush=True)
        pg.wait_for_timeout(3000)


def main(names: list[str]) -> None:
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
            if "/login" in pg.url:
                LoginPage(pg).login()
                pg.goto(settings.base_url + "pharmacies", wait_until="domcontentloaded")
            PharmacySelectionPage(pg).select(name)
            import_products(pg)
            add_suppliers(pg)
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:])
