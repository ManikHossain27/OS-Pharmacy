"""Scenario / combination matrix for the Opening Stock inventory mode.

Same two layers as the other modes:

* ``calc_matrix()``   - thousands of *pure* combinations fed to the oracle (no browser, seconds);
* ``e2e_scenarios()`` - curated cart shape x discount journeys through the real create form -> cart -> checkout ->
                        record details (each one creates a real inventory).

Lines are entered by Retail Price/Box (+ optional Opening Stock %, or a manual BTP + VAT/Box): the form derives
BTP + VAT/Box = Retail x (1 - %/100), and the tests read that back and compare it with ``utils.opening_calc``.
"""
from __future__ import annotations

import itertools
from dataclasses import replace
from typing import Iterator

from utils.inventory_scenarios import DISCOUNTS, LineSpec, Scenario
from utils.opening_calc import opening_line
from utils.inventory_calc import Line

_PLAIN = LineSpec("P0", box_qty=2, retail=100, wholesale=90, min_qty=5, rack="A1")                       # 12 % -> 88
_PLAIN2 = LineSpec("P1", box_qty=3, retail=200, wholesale=180, min_qty=2, rack="B2", opening_pct=15)     # 15 % -> 170
_PLAIN3 = LineSpec("P2", box_qty=1, retail=120, wholesale=100, min_qty=0, rack="C3", opening_pct=20)     # 20 % -> 96
_MANUAL = LineSpec("P1", box_qty=2, retail=100, wholesale=90, btp_vat_per_box=70, rack="D4")             # manual override
_FREE = LineSpec("P1", box_qty=3, retail=40, wholesale=35, free_qty=5, min_qty=1, rack="D4")             # 12 % -> 35.2
_FREE2 = LineSpec("P2", box_qty=2, retail=90, wholesale=80, free_qty=10, rack="E5", opening_pct=10)     # 10 % -> 81
_SPECIAL = LineSpec("P0", box_qty=2, retail=100, wholesale=90, special=20)                              # Special Tk 20
_BIGQTY = LineSpec("P0", box_qty=250, retail=10, wholesale=9)                                           # 8.8
_EXP = LineSpec("P1", box_qty=4, retail=75, wholesale=65, expiry=(15, "Dec", 2035))                     # 66
_FRACTION = LineSpec("P0", box_qty=3, retail=33.33, wholesale=30, opening_pct=7.5)                      # 30.83 (30.8303 rounded)

CART_SHAPES: dict[str, tuple[LineSpec, ...]] = {
    "single_plain": (_PLAIN,),
    "single_manual_btp": (_MANUAL,),
    "single_free": (_FREE,),
    "two_plain": (_PLAIN, _PLAIN2),
    "two_one_free": (_PLAIN, _FREE),
    "three_plain_free_plain": (_PLAIN, _FREE, _PLAIN3),
    "all_free": (_FREE, _FREE2),
    "special_line_with_plain": (_SPECIAL, _PLAIN2),
    "large_qty_with_expiry": (_BIGQTY, _EXP),
    "fraction_rounding": (_FRACTION,),
}


def e2e_scenarios() -> list[Scenario]:
    """Cart shape x discount - every combination (10 x 4 = 40 journeys; one line per product - the cart rule)."""
    out: list[Scenario] = []
    for (shape, lines), (dname, disc) in itertools.product(CART_SHAPES.items(), DISCOUNTS.items()):
        bugs: list[str] = []
        if disc and any(l.free_qty > 0 for l in lines):
            bugs.append("BUG-INV-001")
        tags = ["smoke"] if (shape == "two_one_free" and dname == "pct10") or (
            shape == "single_plain" and dname == "nodisc") else []
        out.append(Scenario(id=f"os-{shape}-{dname}", lines=lines, discount=disc,
                            tags=tuple(tags), known_bugs=tuple(bugs)))
    return out


# --------------------------------------------------------------------------- pure calc matrix
_QPB = (1, 10, 12, 60)
_BOX = (0.5, 1, 3, 50)
_RETAIL = (0.01, 33.33, 125.75, 612, 999.99)
_PCT_OPEN = (0, 7.5, 12, 33.333, 100)
_FREE_QTY = (0, 10)
_PCT = (0, 10, 33.333, 100)
_FLAT = (0, 50, 777.77)


def calc_matrix() -> Iterator[tuple[str, list[Line], float, float]]:
    """Yield (id, lines, discount pct, discount flat)."""
    for qpb, box, retail, op, free, pct, flat in itertools.product(_QPB, _BOX, _RETAIL, _PCT_OPEN, _FREE_QTY, _PCT, _FLAT):
        if pct and flat:        # the UI takes ONE discount type at a time
            continue
        yield (f"1L-q{qpb}-b{box}-r{retail}-op{op}-f{free}-pct{pct}-flat{flat}",
               [opening_line(box, qpb, retail, pct=op, free_qty=free)], pct, flat)
    shapes = [opening_line(2, 10, 100), opening_line(3, 12, 200, pct=15, free_qty=5), opening_line(1, 1, 120, pct=20),
              opening_line(5, 60, 10, free_qty=10), opening_line(10, 6, 612, pct=0)]
    for r in (2, 3, 4, 5):
        for combo in itertools.combinations(range(len(shapes)), r):
            for pct, flat in ((0, 0), (10, 0), (7.5, 0), (0, 50), (0, 777.77)):
                yield (f"{r}L-{'_'.join(map(str, combo))}-pct{pct}-flat{flat}",
                       [replace(shapes[i]) for i in combo], pct, flat)
