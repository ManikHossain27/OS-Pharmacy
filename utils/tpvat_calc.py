"""Pure-Python oracle for the TP/VAT inventory mode.

Mirrors, formula for formula, the ``TP per vat mode (2)`` sheet of
``Knowledge/Inventory Management/PMS_Innventory Calculation (Non Rounded).xlsx``
(cell references in comments).  ``tools/validate_tpvat_oracle.py`` proves it against
the workbook with random products, so the chain of trust is the same as Default mode:

    workbook  ==(validated)==  oracle  ==(asserted)==  create form / cart / checkout / details

Rules that differ from the Default-mode sheet (all in the workbook, all confirmed against
the application on 2026-10-11):

* purchase cost = TP + VAT per box; the discount applies to **TP only** (spec 38) - VAT is never discounted;
* **VAT is also charged on free pieces** (AC = TP + VAT x boxes + VAT/pc x free).  The knowledge file's
  spec 38/40 example (``(15+10) x 2 / 30 = 1.66``) leaves it out; the sheet AND the app give ``60 / 30 = 2.00``;
* the Round Off share (AA) is spread over the TP **after** discount (J - R);
* the final price is ``ROUND(Total Price TP+VAT - Discount, 0)``.

Switches (``free_vat``, ``less_rule``) only exist to describe known sheet quirks; the defaults reproduce the sheet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from utils.inventory_calc import excel_round

SYSTEM_VAT_RATE = 0.174        # sheet G1 / spec section 11


@dataclass
class TpVatLine:
    """One cart line (sheet columns B, C, E, F, H, K, M, S)."""
    box_qty: float
    qty_per_box: float
    tp_per_box: float
    vat_per_box: float
    free_qty: float = 0
    retail_per_box: float = 0
    wholesale_per_box: float = 0
    special_discount: float = 0           # col S - manual per-line discount value (form field "Special Discount (Tk)")
    name: str = ""

    # ---- derived by TpVatInventory.calculate() --------------------------
    total_qty: float = 0                  # D = B*C
    total_tp: float = 0                   # J = F*B
    total_price: Optional[float] = None   # AC (None == "" in the sheet)
    discount_pct: float = 0               # Q
    discount_value: float = 0             # R
    less_amount: Optional[float] = None   # Z
    round_adj: Optional[float] = None     # AA
    purchase_price_pc: Optional[float] = None    # T
    purchase_price_box: Optional[float] = None   # U
    final_line_cost: Optional[float] = None      # AB
    retail_margin_pct: Optional[float] = None    # V
    retail_margin_value: Optional[float] = None  # W
    wholesale_margin_pct: Optional[float] = None   # X
    wholesale_margin_value: Optional[float] = None  # Y
    sheet_error: Optional[str] = None

    def __post_init__(self) -> None:
        # D, J and AC only depend on the line itself, so they are valid immediately (the cart / form checks read
        # them before any discount is computed; AC uses the sheet rule - VAT also on free pieces).
        self.total_qty = self.box_qty * self.qty_per_box
        self.total_tp = self.tp_per_box * self.box_qty
        if self.qty_per_box > 0 and self.box_qty != 0:
            self.total_price = (self.total_tp + self.vat_per_box * self.box_qty
                                + (self.vat_per_box / self.qty_per_box) * self.free_qty)

    @property
    def physical_qty(self) -> float:
        return self.total_qty + self.free_qty

    @property
    def total_vat(self) -> float:
        """VAT carried by the line (on purchased boxes AND free pieces under the sheet rule)."""
        return (self.total_price - self.total_tp) if self.total_price is not None else 0.0


@dataclass
class TpVatInventory:
    lines: list[TpVatLine] = field(default_factory=list)
    discount_pct: float = 0               # I1 (fraction)
    discount_flat: float = 0              # I2
    paid: float = 0                       # K4
    supplier_balance: float = 0           # M2 (+ we owe, - advance)
    less: float = 0                       # M5
    free_vat: bool = True                 # AC / T charge VAT on free pieces (sheet + app); False = knowledge-file example
    less_rule: str = "sheet"              # "sheet": Z = M5/K1*J, divided by D;  "total": M5/G2 x price, divided by D+E

    # ---- totals -----------------------------------------------------------
    total_price: float = 0                # G2 (= AC5)
    total_tp: float = 0                   # G3
    total_vat: float = 0                  # G4
    eligible_tp: float = 0                # I3
    total_discount: float = 0             # I4
    final_price: float = 0                # K2
    round_adjustment: float = 0           # K3
    due: float = 0                        # M3
    advance: float = 0                    # M4
    sum_special: float = 0                # S5
    k1: float = 0                         # K1 (sheet quirk: sum of per-box TP + VAT)

    def calculate(self) -> "TpVatInventory":
        L = self.lines
        for l in L:
            l.total_qty = l.box_qty * l.qty_per_box
            l.total_tp = l.tp_per_box * l.box_qty
            if l.qty_per_box <= 0 or l.box_qty == 0:                       # AC: blank
                l.total_price = None
            else:
                free_vat = (l.vat_per_box / l.qty_per_box) * l.free_qty if self.free_vat else 0.0
                l.total_price = l.total_tp + l.vat_per_box * l.box_qty + free_vat   # AC
        self.total_price = sum(l.total_price for l in L if l.total_price is not None)     # G2 / AC5
        self.total_tp = sum(l.total_tp for l in L)                                        # G3
        self.total_vat = self.total_price - self.total_tp                                 # G4
        self.sum_special = sum(l.special_discount for l in L)                             # S5
        self.eligible_tp = sum(l.total_tp for l in L if l.free_qty <= 0 and l.special_discount <= 0)   # I3
        self.k1 = sum(l.tp_per_box + l.vat_per_box for l in L if l.box_qty > 0)           # K1
        if self.discount_flat > 0:
            rate = (max(self.discount_flat - self.sum_special, 0) / self.eligible_tp) if self.eligible_tp > 0 else 0
        else:
            rate = self.discount_pct
        for l in L:
            if l.special_discount > 0:
                l.discount_value = l.special_discount
                l.discount_pct = l.special_discount / l.total_tp if l.total_tp > 0 else 0
            elif l.free_qty > 0:
                l.discount_value = 0
                l.discount_pct = 0
            else:
                l.discount_value = l.total_tp * rate
                l.discount_pct = rate
        self.total_discount = sum(l.discount_value for l in L)                            # I4
        self.final_price = excel_round(self.total_price - self.total_discount)            # K2
        self.round_adjustment = self.final_price - (self.total_price - self.total_discount)   # K3
        tp_after = self.total_tp - self.total_discount                                    # G3 - I4
        for l in L:
            has_j = l.total_tp != 0
            # Z (Less per product)
            if self.less_rule == "sheet":
                l.less_amount = (self.less / self.k1 * l.total_tp) if has_j and self.k1 != 0 else None
            else:
                l.less_amount = (self.less / self.total_price * (l.total_price or 0)) \
                    if (l.total_price or 0) != 0 and self.total_price != 0 else None
            # AA (Round Adj per product): share of K3 over TP after discount
            l.round_adj = (self.round_adjustment / tp_after * (l.total_tp - l.discount_value)) \
                if has_j and tp_after != 0 else None
            phys = l.total_qty + l.free_qty
            l.sheet_error = None
            if l.box_qty == 0 or l.qty_per_box <= 0 or phys <= 0:                         # T guard -> ""
                l.purchase_price_pc = None
            else:
                free_vat = (l.vat_per_box / l.qty_per_box) * l.free_qty if self.free_vat else 0.0
                t = ((l.tp_per_box + l.vat_per_box) * l.box_qty + free_vat - l.discount_value) / phys
                # IF(Z>=0, Z/D, 0): a blank Z ("" >= 0 is TRUE in Excel) makes Z/D #VALUE!
                if l.less_amount is None:
                    l.sheet_error = "#VALUE!"
                elif l.less_amount >= 0:
                    divisor = l.total_qty if self.less_rule == "sheet" else phys
                    if divisor == 0:
                        l.sheet_error = "#DIV/0!"
                    else:
                        t -= l.less_amount / divisor
                if l.round_adj is not None:
                    t += l.round_adj / phys
                l.purchase_price_pc = None if l.sheet_error else t
            ok = l.purchase_price_pc is not None
            l.purchase_price_box = l.purchase_price_pc * l.qty_per_box if ok else None    # U
            l.final_line_cost = (l.purchase_price_pc * phys if ok and l.purchase_price_pc != 0 and l.total_qty != 0
                                 else None)                                                # AB
            if ok and l.retail_per_box > 0:
                l.retail_margin_pct = (l.retail_per_box - l.purchase_price_box) / l.retail_per_box    # V
                l.retail_margin_value = (l.retail_per_box - l.purchase_price_box) if l.purchase_price_box else None  # W
            else:
                l.retail_margin_pct = l.retail_margin_value = None
            if ok and l.wholesale_per_box > 0:
                l.wholesale_margin_pct = (l.wholesale_per_box - l.purchase_price_box) / l.wholesale_per_box   # X
                l.wholesale_margin_value = (l.wholesale_per_box - l.purchase_price_box) if l.purchase_price_box else None  # Y
            else:
                l.wholesale_margin_pct = l.wholesale_margin_value = None
        net = self.supplier_balance + self.final_price - self.paid      # M2+K2-K4 (the TP/VAT sheet does NOT deduct Less)
        self.due = max(net, 0)                                          # M3
        self.advance = max(-net, 0)                                     # M4
        return self

    # ---- UI-facing figures ---------------------------------------------------
    @property
    def general_discount(self) -> float:
        """Checkout 'General Discount (on TP)': eligible lines only, Special excluded."""
        return self.total_discount - self.sum_special_applied

    @property
    def sum_special_applied(self) -> float:
        return sum(l.discount_value for l in self.lines if l.special_discount > 0)

    @property
    def eligible_lines(self) -> list[TpVatLine]:
        return [l for l in self.lines if l.free_qty <= 0 and l.special_discount <= 0]


def build(lines: Iterable[TpVatLine], *, pct: float = 0, flat: float = 0, paid: float = 0,
          supplier_balance: float = 0, less: float = 0, free_vat: bool = True,
          less_rule: str = "sheet") -> TpVatInventory:
    """``pct`` is in percent (10 == 10 %), as typed in the checkout UI."""
    return TpVatInventory(lines=list(lines), discount_pct=pct / 100.0, discount_flat=flat, paid=paid,
                          supplier_balance=supplier_balance, less=less, free_vat=free_vat,
                          less_rule=less_rule).calculate()


def vat_for(tp: float, rate: float = SYSTEM_VAT_RATE) -> float:
    """VAT/Box the form pre-fills for a typed TP/Box (sheet H: ROUND(F x rate, 2); verified live: 100 -> 17.4, 89.44 -> 15.56)."""
    return round(tp * rate + 1e-9, 2)
