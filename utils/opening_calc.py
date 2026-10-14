"""Pure-Python oracle for the Opening Stock inventory mode.

The ``Opening Stock`` sheet of ``Knowledge/Inventory Management/PMS_Innventory Calculation (Non Rounded).xlsx``
is the Default sheet with ONE difference: the purchase cost per box (BTP + VAT/Box, col I) is not typed, it is
derived from the retail price and the Opening Stock percentage (col F):

    BTP + VAT/Box = Retail Price/Box x (1 - Opening Stock % / 100)          (sheet I = G x (1 - F))

Everything after that (totals, discount, special, free qty, round-off, Less, purchase price, margins) is the
Default-mode calculation, so this module only adds the derivation and re-uses ``utils.inventory_calc``:

    workbook  ==(validated, tools/validate_opening_oracle.py)==  oracle  ==(asserted)==  form / cart / checkout / details

Rules confirmed live on 2026-10-12 (staging, Manik Pharma):

* default Opening Stock % is 12 and is re-set to 12 whenever another product is selected;
* BTP + VAT/Box is ROUND(Retail x (1 - %/100), 2); the % is clamped to 0..100;
* editing Retail Price/Box or the % re-derives BTP + VAT/Box; typing BTP + VAT/Box sets Total = BTP x Box Qty;
* Total BTP + VAT edit -> BTP + VAT/Box = Total / Box Qty.
"""
from __future__ import annotations

from typing import Optional

from utils.inventory_calc import Inventory, Line, build, excel_round

DEFAULT_PCT = 12.0


def clamp_pct(pct: float) -> float:
    """The form clamps the percentage into 0..100 (typing -5 gives 0, 150 gives 100)."""
    return min(max(pct, 0.0), 100.0)


def btp_for(retail: float, pct: float = DEFAULT_PCT) -> float:
    """BTP + VAT/Box the APPLICATION shows: the sheet's exact value rounded to 2 decimals."""
    return excel_round(retail * (1 - clamp_pct(pct) / 100.0), 2)


def btp_exact(retail: float, pct: float = DEFAULT_PCT) -> float:
    """BTP + VAT/Box exactly as the SHEET computes it (col I, no rounding)."""
    return retail * (1 - pct / 100.0)


def pct_for(retail: float, btp: float) -> Optional[float]:
    """Opening Stock % implied by a manual BTP + VAT/Box (spec section 19: retail 100, BTP 80 -> 20 %)."""
    return (retail - btp) / retail * 100.0 if retail > 0 else None


def opening_line(box_qty: float, qty_per_box: float, retail: float, *, pct: float = DEFAULT_PCT,
                 btp: Optional[float] = None, free_qty: float = 0, wholesale: float = 0, special: float = 0,
                 name: str = "", exact: bool = False) -> Line:
    """One cart line. ``btp`` is a manual override; otherwise it is derived from retail and ``pct``."""
    if btp is None:
        btp = btp_exact(retail, pct) if exact else btp_for(retail, pct)
    return Line(box_qty=box_qty, qty_per_box=qty_per_box, btp_vat_per_box=btp, free_qty=free_qty,
                retail_per_box=retail, wholesale_per_box=wholesale, special_discount=special, name=name)


def sheet_due_advance(inv: Inventory) -> tuple[float, float]:
    """Supplier Due / Advance as the ``Opening Stock`` sheet (N3 / N4 = N2 + L4 - L5 - N5) computes them - Less is
    deducted, as in the Default sheet (the sheet was corrected 2026-10-12)."""
    net = inv.supplier_balance + inv.final_price - inv.paid - inv.less
    return max(net, 0.0), max(-net, 0.0)


__all__ = ["DEFAULT_PCT", "Inventory", "Line", "build", "btp_for", "btp_exact", "clamp_pct", "excel_round",
           "opening_line", "pct_for", "sheet_due_advance"]
