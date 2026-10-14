"""Unique, clearly-identifiable QA test data.

Every generated value carries the ``QA_Auto`` prefix and a timestamp so records
are easy to spot and never collide with real business data or previous runs.
"""
from __future__ import annotations

import random
import string
from datetime import datetime
from typing import Any

_PREFIX = "QA_Auto"


def _stamp() -> str:
    return datetime.now().strftime("%y%m%d_%H%M%S")


def _rand(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def unique_suffix() -> str:
    return f"{_stamp()}_{_rand()}"


def product_name() -> str:
    return f"{_PREFIX}_Product_{unique_suffix()}"


def company_name() -> str:
    return f"{_PREFIX}_Company_{unique_suffix()}"


def generic_name() -> str:
    return f"{_PREFIX}_Generic_{unique_suffix()}"


def product_type_name() -> str:
    return f"{_PREFIX}_Type_{unique_suffix()}"


def barcode_value() -> str:
    return f"{_PREFIX.upper()}{_stamp().replace('_', '')}"


def new_product(**overrides: Any) -> dict[str, Any]:
    """A valid Add-New-Product payload; override any field via kwargs."""
    data: dict[str, Any] = {
        "product_name": product_name(),
        "strength": "500 mg",
        "product_type": None,   # caller must supply an existing type
        "company": None,        # caller must supply an existing company
        "generic": None,        # optional
        "qty_per_box": 10,
        "cost_per_box": 90,     # since 2026-09-09 the Cost/Box field is enabled + required
        "retail_price_per_box": 120,
        "wholesale_price_per_box": 100,
        "rack_no": 12,
        "barcode_value": barcode_value(),
        "volume": "10 ml",
        "origin": "Bangladesh",
        "medicine": True,
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Boundary / negative string helpers
# ---------------------------------------------------------------------------
UNICODE = "Ünïcödé_药品_✓"
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:',.<>/?`~"


def long_string(length: int = 256, ch: str = "A") -> str:
    return ch * length
