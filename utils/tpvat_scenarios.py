"""Scenario / combination matrix for the TP/VAT inventory mode.

Same two layers as ``utils/inventory_scenarios.py``:

* ``calc_matrix()``     - thousands of pure combinations fed to ``utils.tpvat_calc`` (no browser);
* ``e2e_scenarios()``   - curated real create-form -> cart -> checkout -> record journeys.

``vat_per_box=None`` in a spec means "leave the VAT/Box the form auto-fills (17.4 % of the typed TP)";
the real value is read back from the form and fed to the oracle, never assumed.
One product appears at most once per cart (business rule, 2026-10-07).
"""
from __future__ import annotations

import itertools
from dataclasses import replace
from typing import Iterator, Optional

from utils.inventory_scenarios import LineSpec, Scenario
from utils.tpvat_calc import TpVatLine, vat_for

# ---- line shapes ---------------------------------------------------------------------------
_PLAIN = LineSpec("P0", box_qty=2, tp_per_box=89.44, retail=150, wholesale=140, min_qty=5, rack="A1")
_PLAIN_VAT = LineSpec("P0", box_qty=2, tp_per_box=100, vat_per_box=5, retail=150, wholesale=140, min_qty=5, rack="A1")
_PLAIN2 = LineSpec("P1", box_qty=3, tp_per_box=125.75, retail=200, wholesale=180, min_qty=2, rack="B2")
_PLAIN3 = LineSpec("P2", box_qty=1, tp_per_box=80, retail=120, wholesale=100, min_qty=0, rack="C3")
_FREE = LineSpec("P1", box_qty=3, tp_per_box=21.6, free_qty=5, retail=40, wholesale=35, min_qty=1, rack="D4")
_FREE2 = LineSpec("P2", box_qty=2, tp_per_box=55.55, free_qty=10, retail=90, wholesale=80, rack="E5")
_SPECIAL = LineSpec("P0", box_qty=2, tp_per_box=100, special=20, retail=150, wholesale=140, rack="F6")
_TP_ZERO = LineSpec("P2", box_qty=2, tp_per_box=0, vat_per_box=5, retail=10, wholesale=8)
_BIGQTY = LineSpec("P0", box_qty=250, tp_per_box=7.2, retail=15, wholesale=12)
_EXP = LineSpec("P1", box_qty=4, tp_per_box=48.5, retail=75, wholesale=65, expiry=(15, "Dec", 2035))

CART_SHAPES: dict[str, tuple[LineSpec, ...]] = {
    "single_plain": (_PLAIN,),
    "single_manual_vat": (_PLAIN_VAT,),
    "single_free": (_FREE,),
    "two_plain": (_PLAIN, _PLAIN2),
    "two_one_free": (_PLAIN, _FREE),
    "three_plain_free_plain": (_PLAIN, _FREE, _PLAIN3),
    "all_free": (_FREE, _FREE2),
    "special_line_with_plain": (_SPECIAL, _PLAIN2),
    "large_qty_with_expiry": (_BIGQTY, _EXP),
    "tp_zero_vat_only": (_PLAIN, _TP_ZERO),
}

DISCOUNTS: dict[str, Optional[tuple[float, str]]] = {
    "nodisc": None,
    "pct10": (10, "%"),
    "pct7_5": (7.5, "%"),
    "flat50": (50, "Tk"),
}


def e2e_scenarios() -> list[Scenario]:
    """Cart shape x discount: 10 x 4 = 40 journeys."""
    out: list[Scenario] = []
    for (shape, lines), (dname, disc) in itertools.product(CART_SHAPES.items(), DISCOUNTS.items()):
        bugs: list[str] = []
        if shape == "tp_zero_vat_only":
            bugs.append("WORKBOOK-GAP-TPVAT-2")      # sheet col T is #VALUE! for a zero-TP line
        tags = ["smoke"] if (shape == "two_one_free" and dname == "pct10") or (
            shape == "single_plain" and dname == "nodisc") else []
        out.append(Scenario(id=f"tv-{shape}-{dname}", lines=lines, discount=disc,
                            tags=tuple(tags), known_bugs=tuple(bugs)))
    return out


# ---- pure calc matrix --------------------------------------------------------------------------
_QPB = (1, 3, 10, 12, 60)
_BOX = (0.5, 1, 2, 7, 50)
_TP = (0.01, 33.3, 125.75, 612, 999.99)
_VAT_MODE = ("auto", "manual", "zero")      # 17.4 % of TP / a typed amount (4.5) / VAT/Box = 0
_FREE_QTY = (0, 1, 10)
_PCT = (0, 5, 7.5, 10, 33.333, 100)
_FLAT = (0, 1, 50, 777.77)


def _vat(tp: float, mode: str) -> float:
    return {"auto": vat_for(tp), "manual": 4.5, "zero": 0.0}[mode]


def calc_matrix() -> Iterator[tuple[str, list[TpVatLine], float, float]]:
    """Yield (id, lines, pct, flat). Single-line grid over every dimension plus multi-line combinations."""
    for qpb, box, tp, vm, free, pct, flat in itertools.product(_QPB, _BOX, _TP, _VAT_MODE, _FREE_QTY, _PCT, _FLAT):
        if pct and flat:        # the UI takes ONE discount type at a time
            continue
        yield (f"1L-q{qpb}-b{box}-tp{tp}-{vm}-f{free}-pct{pct}-flat{flat}",
               [TpVatLine(box, qpb, tp, _vat(tp, vm), free_qty=free)], pct, flat)
    shapes = [TpVatLine(2, 10, 89.44, 15.56), TpVatLine(3, 12, 125.75, 21.88, free_qty=5),
              TpVatLine(1, 1, 80, 13.92), TpVatLine(5, 60, 7.2, 1.25, free_qty=10),
              TpVatLine(10, 6, 612, 5, special_discount=40)]
    for r in (2, 3, 4, 5):
        for combo in itertools.combinations(range(len(shapes)), r):
            for pct, flat in ((0, 0), (10, 0), (7.5, 0), (0, 50), (0, 777.77)):
                yield (f"{r}L-{'_'.join(map(str, combo))}-pct{pct}-flat{flat}",
                       [replace(shapes[i]) for i in combo], pct, flat)
