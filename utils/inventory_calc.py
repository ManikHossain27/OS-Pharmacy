"""Pure-Python oracle for the Default inventory mode.

Mirrors, formula for formula, the ``Default Mode (2)`` sheet of
``Knowledge/Inventory Management/PMS_Innventory Calculation (Non Rounded).xlsx``
(cells referenced in comments).  Tests compare the application against this
oracle, and ``tools/validate_inventory_oracle.py`` proves the oracle against the
workbook itself with hundreds of random products, so the chain of trust is:

    workbook  ==(validated)==  oracle  ==(asserted)==  create form / cart /
                                                       checkout / record details

No browser, no I/O: importable from any test or tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional

EPS = 1e-9


def excel_round(value: float, digits: int = 0) -> float:
    """Excel ROUND(): half away from zero (Python's round() is banker's)."""
    q = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))


@dataclass
class Line:
    """One cart line (sheet columns B, C, E, F, H, J, P)."""
    box_qty: float
    qty_per_box: float
    btp_vat_per_box: float
    free_qty: float = 0
    retail_per_box: float = 0
    wholesale_per_box: float = 0
    special_discount: float = 0          # col P - manual per-line discount value
    name: str = ""

    # ---- derived by Inventory.calculate() -------------------------------
    total_qty: float = 0                 # D = B*C
    total_btp_vat: float = 0             # G = F*B
    discount_pct: float = 0              # N
    discount_value: float = 0            # O
    less_amount: Optional[float] = None  # W
    round_adj: Optional[float] = None    # X
    purchase_price_pc: Optional[float] = None   # Q (None == "" in the sheet)
    purchase_price_box: Optional[float] = None  # R
    final_line_cost: Optional[float] = None     # Y
    retail_margin_pct: Optional[float] = None   # S
    retail_margin_value: Optional[float] = None  # T
    wholesale_margin_pct: Optional[float] = None  # U
    wholesale_margin_value: Optional[float] = None  # V
    sheet_error: Optional[str] = None    # '#DIV/0!' / '#VALUE!' where the sheet itself errors

    def __post_init__(self) -> None:
        # D and G only depend on the line itself, so they are valid immediately
        # (the cart / form checks read them before any discount is computed).
        self.total_qty = self.box_qty * self.qty_per_box
        self.total_btp_vat = self.btp_vat_per_box * self.box_qty

    @property
    def physical_qty(self) -> float:
        return self.total_qty + self.free_qty


@dataclass
class Inventory:
    lines: list[Line] = field(default_factory=list)
    discount_pct: float = 0      # I2 (stored as a fraction: 0.1 == 10 %)
    discount_flat: float = 0     # I3
    less: float = 0              # M5
    paid: float = 0              # K5
    supplier_balance: float = 0  # M2 (+ = we owe supplier, - = advance)
    # How Round Off (I1) is shared between lines:
    #   "post_discount" - in proportion to each line's AFTER-discount amount (G - O). This is the
    #                     APPLICATION's rule and the one the user confirmed correct (2026-10-08).
    #   "pre_discount"  - in proportion to the pre-discount BTP+VAT (G), as the workbook's col X does.
    #                     Kept only so tools/validate_inventory_oracle.py can reproduce the sheet cell by cell.
    round_basis: str = "post_discount"
    # How "Less" (W) is turned into a per-piece reduction:
    #   "physical"  - W / (Qty + Free Qty): the APPLICATION's rule (verified live 2026-10-11: the line cost shown on
    #                 Inventory Details = Total - Less share + Round share, and the lines add up to Final - Less).
    #   "purchased" - W / Qty, as workbook col Q does; over-reduces a line that carries Free Qty. Reference only
    #                 (tools/validate_inventory_oracle.py).
    less_basis: str = "physical"

    # ---- totals (filled by calculate) -----------------------------------
    total_price: float = 0       # K3
    eligible_base: float = 0     # I4
    total_discount: float = 0    # K2
    final_price: float = 0       # K4 (rounded to whole currency unit)
    round_adjustment: float = 0  # I1
    due: float = 0              # M3
    advance: float = 0          # M4
    total_qty: float = 0         # D5
    total_box_qty: float = 0     # B5

    def calculate(self) -> "Inventory":
        L = self.lines
        for l in L:
            l.total_qty = l.box_qty * l.qty_per_box                      # D
            l.total_btp_vat = l.btp_vat_per_box * l.box_qty              # G
        self.total_price = sum(l.total_btp_vat for l in L)               # K3
        self.total_qty = sum(l.total_qty for l in L)
        self.total_box_qty = sum(l.box_qty for l in L)
        sum_special = sum(l.special_discount for l in L)                 # P5
        # I4: lines with no free qty AND no positive special discount
        self.eligible_base = sum(
            l.total_btp_vat for l in L if l.free_qty <= 0 and l.special_discount <= 0
        )
        if self.discount_flat > 0:                                       # N/O rate
            rate = (max(self.discount_flat - sum_special, 0) / self.eligible_base
                    if self.eligible_base > 0 else 0)
        else:
            rate = self.discount_pct
        for l in L:
            if l.special_discount > 0:
                l.discount_value = l.special_discount
                l.discount_pct = l.special_discount / l.total_btp_vat if l.total_btp_vat > 0 else 0
            elif l.free_qty > 0:
                l.discount_value = 0
                l.discount_pct = 0
            else:
                l.discount_value = l.total_btp_vat * rate
                l.discount_pct = rate
        self.total_discount = sum(l.discount_value for l in L)           # K2
        self.final_price = excel_round(self.total_price - self.total_discount)  # K4
        self.round_adjustment = self.final_price - (self.total_price - self.total_discount)  # I1
        for l in L:
            has_g = l.total_btp_vat != 0
            l.less_amount = (self.less / self.total_price * l.total_btp_vat
                             if has_g and self.total_price != 0 else None)           # W
            if self.round_basis == "pre_discount":                                   # workbook col X
                l.round_adj = (self.round_adjustment / self.total_price * l.total_btp_vat
                               if has_g and self.total_price != 0 else None)
            else:                                                                    # app rule
                payable = self.total_price - self.total_discount
                l.round_adj = (self.round_adjustment / payable * (l.total_btp_vat - l.discount_value)
                               if has_g and payable != 0 else None)
            phys = l.total_qty + l.free_qty
            l.sheet_error = None
            # Q = "" when Box Qty is 0/blank, Qty/Box <= 0 or there is no physical qty (sheet Q guard,
            # updated 2026-10-08) - a free-only line therefore has NO purchase price instead of an error.
            if l.box_qty == 0 or l.qty_per_box <= 0 or phys <= 0:
                l.purchase_price_pc = None                                           # Q == ""
            else:
                q = (l.total_btp_vat - l.discount_value) / phys
                # Excel: IF(W>=0, W/D, 0). "" >= 0 is TRUE, so a blank W (G=0) makes W/D #VALUE!,
                # and D=0 (free-only line) makes it #DIV/0!.
                if l.less_amount is None:
                    l.sheet_error = "#VALUE!"
                elif l.less_amount >= 0:
                    divisor = phys if self.less_basis == "physical" else l.total_qty
                    if divisor == 0:
                        l.sheet_error = "#DIV/0!"
                    else:
                        q -= l.less_amount / divisor
                if l.round_adj is not None:
                    q += l.round_adj / phys
                l.purchase_price_pc = None if l.sheet_error else q
            ok = l.purchase_price_pc is not None
            l.purchase_price_box = l.purchase_price_pc * l.qty_per_box if ok else None   # R
            l.final_line_cost = (l.purchase_price_pc * phys if ok and l.purchase_price_pc != 0 else None)  # Y
            if ok and l.retail_per_box > 0:
                l.retail_margin_pct = (l.retail_per_box - l.purchase_price_box) / l.retail_per_box   # S
                l.retail_margin_value = (l.retail_per_box - l.purchase_price_box) if l.purchase_price_box else None
            else:
                l.retail_margin_pct = l.retail_margin_value = None
            if ok and l.wholesale_per_box > 0:
                l.wholesale_margin_pct = (l.wholesale_per_box - l.purchase_price_box) / l.wholesale_per_box  # U
                l.wholesale_margin_value = (l.wholesale_per_box - l.purchase_price_box) if l.purchase_price_box else None
            else:
                l.wholesale_margin_pct = l.wholesale_margin_value = None
        net = self.supplier_balance + self.final_price - self.paid - self.less   # M2+K4-K5-M5 (Less deducted)
        self.due = max(net, 0)                                                # M3
        self.advance = max(-net, 0)                                           # M4
        return self

    # convenience ----------------------------------------------------------
    @property
    def eligible_lines(self) -> list[Line]:
        return [l for l in self.lines if l.free_qty <= 0 and l.special_discount <= 0]


def build(lines: Iterable[Line], *, pct: float = 0, flat: float = 0, paid: float = 0,
          supplier_balance: float = 0, less: float = 0, round_basis: str = "post_discount",
          less_basis: str = "physical") -> Inventory:
    """``pct`` is given in percent (10 == 10 %), as typed in the checkout UI."""
    return Inventory(lines=list(lines), discount_pct=pct / 100.0, discount_flat=flat,
                     paid=paid, supplier_balance=supplier_balance, less=less,
                     round_basis=round_basis, less_basis=less_basis).calculate()


def approx(a: float, b: float, tol: float = 0.011) -> bool:
    return abs(a - b) <= tol
