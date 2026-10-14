"""Scenario / combination matrix for the Default inventory mode.

Two layers, deliberately separate:

* ``calc_matrix()``       - thousands of *pure* combinations fed to the oracle
                            (no browser, runs in seconds).
* ``e2e_scenarios()``     - a curated, still exhaustive-by-dimension set of
                            real create-form -> cart -> checkout -> record
                            journeys (each creates one real inventory).

Product references are symbolic (``"P0"``, ``"P1"``, ``"P2"``) and resolved at
run time from ``test_data/inventory_data.json`` so the data file - not the test
code - decides which catalogue products are used.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from typing import Iterator, Optional

from utils.inventory_calc import Line

# --------------------------------------------------------------------------- UI scenarios


@dataclass(frozen=True)
class LineSpec:
    product: str = "P0"                    # P0 / P1 / P2 -> catalogue product
    box_qty: float = 1
    btp_vat_per_box: Optional[float] = None  # None => keep the preloaded product value
    free_qty: int = 0
    retail: Optional[float] = None
    wholesale: Optional[float] = None
    min_qty: Optional[int] = None
    rack: Optional[str] = None
    batch: Optional[str] = None            # None => unique QA batch generated per run
    expiry: Optional[tuple[int, str, int]] = None   # (day, "Mon", year)
    barcode: Optional[str] = None
    tp_per_box: Optional[float] = None     # TP/VAT mode only
    vat_per_box: Optional[float] = None    # TP/VAT mode only; None => the form's auto VAT (17.4 % of TP)
    special: float = 0                     # "Special Discount (Tk)" - manual per-line discount value
    opening_pct: Optional[float] = None    # Opening Stock mode only; None => keep the form's default (12 %)


@dataclass(frozen=True)
class Scenario:
    id: str
    lines: tuple[LineSpec, ...]
    discount: Optional[tuple[float, str]] = None    # (value, "%" | "Tk")
    paid: Optional[float] = None                    # None => pay the Final Price in full
    payment_method: str = "Cash"
    inventory_type: str = "Purchase"
    tags: tuple[str, ...] = ()
    known_bugs: tuple[str, ...] = ()


# Line "shapes" - every structural way a cart can look.
_PLAIN = LineSpec("P0", box_qty=2, btp_vat_per_box=33.3, retail=60, wholesale=50, min_qty=5, rack="A1")
_PLAIN2 = LineSpec("P1", box_qty=3, btp_vat_per_box=125.75, retail=200, wholesale=180, min_qty=2, rack="B2")
_PLAIN3 = LineSpec("P2", box_qty=1, btp_vat_per_box=80, retail=120, wholesale=100, min_qty=0, rack="C3")
_FREE = LineSpec("P1", box_qty=3, btp_vat_per_box=21.6, free_qty=5, retail=40, wholesale=35, min_qty=1, rack="D4")
_FREE2 = LineSpec("P2", box_qty=2, btp_vat_per_box=55.55, free_qty=10, retail=90, wholesale=80, rack="E5")
_ZERO = LineSpec("P2", box_qty=2, btp_vat_per_box=0, retail=10, wholesale=8)
_BIGQTY = LineSpec("P0", box_qty=250, btp_vat_per_box=7.2, retail=10, wholesale=9)
_EXP = LineSpec("P1", box_qty=4, btp_vat_per_box=48.5, retail=75, wholesale=65, expiry=(15, "Dec", 2035))

CART_SHAPES: dict[str, tuple[LineSpec, ...]] = {
    "single_plain": (_PLAIN,),
    "single_free": (_FREE,),
    "two_plain": (_PLAIN, _PLAIN2),
    "two_one_free": (_PLAIN, _FREE),
    "three_plain_free_plain": (_PLAIN, _FREE, _PLAIN3),
    "all_free": (_FREE, _FREE2),
    "large_qty_with_expiry": (_BIGQTY, _EXP),
    "zero_price_line": (_PLAIN, _ZERO),
}

DISCOUNTS: dict[str, Optional[tuple[float, str]]] = {
    "nodisc": None,
    "pct10": (10, "%"),
    "pct7_5": (7.5, "%"),
    "flat50": (50, "Tk"),
}

# Known defects (test_data/bug_logs.json) that make a given dimension fail.
_BUGS_BY_DISCOUNT = {"flat50": ("BUG-INV-020",)}


def e2e_scenarios() -> list[Scenario]:
    """Cart shape x discount - every combination (8 x 4 = 32 journeys; one line per product - see the cart rule)."""
    out: list[Scenario] = []
    for (shape, lines), (dname, disc) in itertools.product(CART_SHAPES.items(), DISCOUNTS.items()):
        bugs = list(_BUGS_BY_DISCOUNT.get(dname, ()))
        if disc and any(l.free_qty > 0 for l in lines):
            bugs.append("BUG-INV-001")
        tags = ["smoke"] if (shape == "two_one_free" and dname == "pct10") or (
            shape == "single_plain" and dname == "nodisc") else []
        out.append(Scenario(id=f"{shape}-{dname}", lines=lines, discount=disc,
                            tags=tuple(tags), known_bugs=tuple(bugs)))
    return out


# Paid-amount / supplier-balance dimension: Final Price is computed at run time, so 'paid' is a ratio.
PAID_RATIOS = {"full": 1.0, "partial_half": 0.5, "zero": 0.0, "over_by_100": None}  # None => final + 100


# --------------------------------------------------------------------------- pure calc matrix

_QPB = (1, 3, 10, 12, 60)
_BOX = (0.5, 1, 2, 7, 50)
_PRICE = (0.01, 33.3, 125.75, 612, 999.99)
_FREE_QTY = (0, 1, 10)
_PCT = (0, 5, 7.5, 10, 33.333, 100)
_FLAT = (0, 1, 50, 777.77)


def calc_matrix() -> Iterator[tuple[str, list[Line], float, float]]:
    """Yield (id, lines, pct, flat). Single-line grid over every dimension plus
    two-line combinations of the discount-relevant shapes."""
    for qpb, box, price, free, pct, flat in itertools.product(_QPB, _BOX, _PRICE, _FREE_QTY, _PCT, _FLAT):
        if pct and flat:        # the UI takes ONE discount type at a time
            continue
        yield (f"1L-q{qpb}-b{box}-p{price}-f{free}-pct{pct}-flat{flat}",
               [Line(box, qpb, price, free_qty=free)], pct, flat)
    shapes = [Line(2, 10, 33.3), Line(3, 12, 125.75, free_qty=5), Line(1, 1, 80), Line(5, 60, 7.2, free_qty=10),
              Line(10, 6, 612)]
    for r in (2, 3, 4, 5):
        for combo in itertools.combinations(range(len(shapes)), r):
            for pct, flat in ((0, 0), (10, 0), (7.5, 0), (0, 50), (0, 777.77)):
                yield (f"{r}L-{'_'.join(map(str, combo))}-pct{pct}-flat{flat}",
                       [replace(shapes[i]) for i in combo], pct, flat)
