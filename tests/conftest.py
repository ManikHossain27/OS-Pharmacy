"""Test-tree fixtures: page objects wired to an authenticated page inside
Manik Pharma, plus per-test QA-data tracking.
"""
from __future__ import annotations

from typing import Iterator

import pytest

from pages.add_product_page import AddProductPage
from pages.barcode_generator_page import BarcodeGeneratorPage
from pages.company_page import CompanyPage
from pages.generic_page import GenericPage
from pages.inventory_page import InventoryPage
from pages.inventory_record_page import InventoryRecordPage
from pages.my_products_page import MyProductsPage
from pages.product_catalog_page import ProductCatalogPage
from pages.product_type_page import ProductTypePage
from utils.logger import get_logger

log = get_logger("tests.conftest")


@pytest.fixture()
def my_products(page, pharmacy) -> MyProductsPage:
    mp = MyProductsPage(page).open().wait_loaded()
    return mp


@pytest.fixture()
def add_product(my_products) -> AddProductPage:
    return my_products.open_add_product()


@pytest.fixture()
def product_catalog(page, pharmacy) -> ProductCatalogPage:
    return ProductCatalogPage(page).open().wait_loaded()


@pytest.fixture()
def barcode_generator(page, pharmacy) -> BarcodeGeneratorPage:
    return BarcodeGeneratorPage(page).open().wait_loaded()


@pytest.fixture()
def company_list(page, pharmacy) -> CompanyPage:
    return CompanyPage(page).open().wait_loaded()


@pytest.fixture()
def generic_list(page, pharmacy) -> GenericPage:
    return GenericPage(page).open().wait_loaded()


@pytest.fixture()
def product_type_list(page, pharmacy) -> ProductTypePage:
    return ProductTypePage(page).open().wait_loaded()


@pytest.fixture()
def inventory(page, pharmacy) -> InventoryPage:
    """Inventory page in Default mode with an empty cart. Some prior test's
    held/cart data may linger server-side (mode-scoped carts persist across
    navigations) - tests that need a clean cart should assert/clear explicitly."""
    return InventoryPage(page).open("Default")


@pytest.fixture()
def inventory_record(page, pharmacy) -> InventoryRecordPage:
    return InventoryRecordPage(page).open()


@pytest.fixture()
def qa_records() -> Iterator[list[str]]:
    """Collect names of QA records a test creates (for reporting / optional cleanup)."""
    created: list[str] = []
    yield created
    if created:
        log.info("Test created QA records: %s", created)
