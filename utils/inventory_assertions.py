"""Reusable, screen-level assertions for the Default inventory journey.

Every ``check_*`` function compares what a screen DISPLAYS with what the oracle
(utils.inventory_calc) says it should display, and records each comparison on a
``Verifier`` instead of stopping at the first mismatch - so one journey reports
all defects across create form / cart / checkout / record details at once.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import allure

from utils.helpers import money, numbers_in
from utils.inventory_calc import Inventory, Line

TOL = 0.011          # currency tolerance for display-rounded (2 dp) values
ROUND_TOL = 0.51     # Final Price may be whole-unit rounded (sheet K4)


@dataclass
class Verifier:
    stage: str
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    # ---- recording ------------------------------------------------------
    def true(self, label: str, ok: bool, detail: str = "") -> bool:
        self.checks.append((label, bool(ok), detail))
        return bool(ok)

    def eq(self, label: str, actual: Any, expected: Any, tol: float = TOL) -> bool:
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            ok = abs(actual - expected) <= tol
        else:
            ok = actual == expected
        return self.true(label, ok, f"actual={actual!r} expected={expected!r}" + (f" (tol {tol})" if isinstance(expected, float) else ""))

    def contains(self, label: str, haystack: str, needle: str) -> bool:
        return self.true(label, needle.lower() in (haystack or "").lower(), f"{needle!r} not in {haystack!r}")

    def any_number(self, label: str, text: str, candidates: list[float], tol: float = TOL) -> bool:
        import re
        nums = numbers_in(text) + [float(n.replace(",", "")) for n in re.findall(r"(?<![\w.])-\d[\d,]*\.?\d*", text or "")]
        ok = any(abs(n - c) <= tol for n in nums for c in candidates)
        return self.true(label, ok, f"cell {text!r} has none of {candidates}")

    # ---- reporting ------------------------------------------------------
    @property
    def failures(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]

    def report(self) -> str:
        rows = [f"{'PASS' if ok else 'FAIL'} | {label}" + ("" if ok else f" | {detail}") for label, ok, detail in self.checks]
        return f"[{self.stage}] {len(self.checks) - len(self.failures)}/{len(self.checks)} checks passed\n" + "\n".join(rows)

    def attach(self) -> None:
        allure.attach(self.report(), name=f"{self.stage} - checks", attachment_type=allure.attachment_type.TEXT)

    def assert_all(self) -> None:
        self.attach()
        if self.failures:
            raise AssertionError(f"[{self.stage}] {len(self.failures)} of {len(self.checks)} checks failed:\n" +
                                 "\n".join(f"  - {l}: {d}" for l, _, d in self.failures))


def special_total(inv: Inventory) -> float:
    """Sum of per-line Special discounts (sheet col P, only values > 0)."""
    return sum(l.special_discount for l in inv.lines if l.special_discount > 0)


# --------------------------------------------------------------------------- create form
def check_form_after_entry(v: Verifier, form: dict[str, str], line: Line) -> None:
    """Fields of the create form after Box Qty / price were typed (spec 5.3, 8)."""
    num = lambda k: float((form.get(k) or "0").replace(",", "") or 0)
    v.eq("form: Total Qty = Box Qty x Qty/Box", num("total_qty"), line.box_qty * line.qty_per_box)
    v.eq("form: Total BTP+VAT = BTP+VAT/Box x Box Qty", num("total_price"), line.btp_vat_per_box * line.box_qty)


# --------------------------------------------------------------------------- cart
def check_cart(v: Verifier, rows: list[dict[str, str]], lines: list[Line], cart_total: float,
               total_items: int, specs: Optional[list] = None) -> None:
    v.eq("cart: Total Items", total_items, len(lines))
    v.eq("cart: row count", len(rows), len(lines))
    v.eq("cart: Total Price = sum of line totals", cart_total, sum(l.total_btp_vat for l in lines))
    for i, (row, l) in enumerate(zip(rows, lines), 1):
        tag = f"cart row {i} ({l.name})"
        v.contains(f"{tag}: Details shows product", row.get("Details", ""), l.name)
        v.any_number(f"{tag}: Box Qty", row.get("Box Qty", ""), [l.box_qty])
        # the cart header reads "BTP+VAT" in Default mode and "BTP+VAT/Box" in Opening Stock mode
        v.any_number(f"{tag}: BTP+VAT/Box", row.get("BTP+VAT", row.get("BTP+VAT/Box", "")), [l.btp_vat_per_box])
        v.any_number(f"{tag}: Total Price", row.get("Total Price", ""), [l.total_btp_vat])
        free_txt = row.get("Free", "")
        v.any_number(f"{tag}: Free Qty ('-' means 0)", free_txt if any(c.isdigit() for c in free_txt) else "0", [l.free_qty])
        if specs and specs[i - 1].expiry:
            d, mon, y = specs[i - 1].expiry
            v.true(f"{tag}: Exp date shows the chosen expiry", str(y) in row.get("Exp date", "") or mon in row.get("Exp date", ""),
                   f"cell {row.get('Exp date')!r}")


# --------------------------------------------------------------------------- checkout
def check_checkout_summary(v: Verifier, summary: dict[str, float], inv: Inventory, paid: float) -> None:
    raw_final = inv.total_price - inv.total_discount
    v.eq("checkout: Total Price (pre-discount)", summary["total_price"], inv.total_price)
    sp = special_total(inv)
    v.eq("checkout: General Discount (eligible lines only, excludes Special)", summary["discount_amount"], inv.total_discount - sp, tol=TOL)
    v.eq("checkout: Final Price within 0.5 of Total - Discount", summary["final_price"], raw_final, tol=ROUND_TOL)
    v.eq("checkout: Final Price is rounded (sheet K4 = ROUND(Total - Discount))", summary["final_price"], inv.final_price, tol=TOL)
    v.true("checkout: Final Price is a whole number", float(summary["final_price"]).is_integer(), f"{summary['final_price']}")
    v.eq("checkout: Round Off equals the sheet round adjustment (I1)", summary["round_off"], inv.round_adjustment, tol=TOL)
    v.eq("checkout: Special Discount = sum of per-line specials", summary.get("special_discount", 0), sp)
    v.eq("checkout: Total Paid", summary["total_paid"], paid)
    v.eq("checkout: Due", summary["due"], max(inv.final_price - paid, 0), tol=ROUND_TOL)


def check_checkout_rows(v: Verifier, rows: list[dict[str, str]], lines: list[Line]) -> None:
    v.eq("checkout: item rows", len(rows), len(lines))
    for i, (row, l) in enumerate(zip(rows, lines), 1):
        tag = f"checkout row {i} ({l.name})"
        v.contains(f"{tag}: product", row.get("Details", ""), l.name)
        if "Total Price" in row:
            v.any_number(f"{tag}: Total Price", row["Total Price"], [l.total_btp_vat])
        if "Box Qty" in row:
            v.any_number(f"{tag}: Box Qty", row["Box Qty"], [l.box_qty])


# --------------------------------------------------------------------------- record details
def purchase_price_candidates(l: Line) -> list[float]:
    """Per-piece AND per-box purchase price, with and without the sheet's
    whole-unit rounding share (the spec does not say which the view shows)."""
    if l.purchase_price_pc is None:
        return []
    phys = l.total_qty + l.free_qty
    share = (l.round_adj or 0) / phys if phys else 0
    pc = [l.purchase_price_pc, l.purchase_price_pc - share]
    return pc + [p * l.qty_per_box for p in pc]


def check_details_header(v: Verifier, fields: dict[str, str], inv: Inventory, paid: float, status: str,
                         n_lines: int, supplier: Optional[str] = None, mode: str = "Default",
                         less: float = 0.0) -> None:
    """Header + Pricing Breakdown of the Inventory Details page, against the oracle."""
    for required in ("Inventory ID", "Inventory Mode", "Supplier Name", "Supplier Phone Number",
                     "Inventory Date & Time", "Received By", "Total Items", "Total Price (TP+VAT)",
                     "General Discount", "Special Discount", "Round Off", "Final Price", "Total Paid", "Payment Status"):
        v.true(f"details: '{required}' is shown", required in fields, "label not rendered")
    if "Inventory ID" in fields:
        v.true("details: Inventory ID format", fields["Inventory ID"].startswith("#INV_"), fields["Inventory ID"])
    if "Inventory Mode" in fields:
        v.eq("details: Inventory Mode is the source mode (spec 44)", fields["Inventory Mode"].strip(), mode)
    if supplier and "Supplier Name" in fields:
        v.contains("details: supplier", fields["Supplier Name"], supplier)
    if "Total Items" in fields:
        v.any_number("details: Total Items", fields["Total Items"], [n_lines])
    if "Total Price (TP+VAT)" in fields:
        v.eq("details: Total Price (TP+VAT) = checkout total", money(fields["Total Price (TP+VAT)"]), inv.total_price)
    if "General Discount" in fields:
        v.eq("details: General Discount (excludes Special)", money(fields["General Discount"]), inv.total_discount - special_total(inv))
    if "Special Discount" in fields:
        v.eq("details: Special Discount = sum of per-line specials", money(fields["Special Discount"]), special_total(inv))
    if "Round Off" in fields:
        v.eq("details: Round Off = sheet round adjustment", money(fields["Round Off"]), inv.round_adjustment)
    if "Final Price" in fields:
        v.eq("details: Final Price is rounded (sheet K4) and equals checkout" + (" minus Less (Less & Buy)" if less else ""),
             money(fields["Final Price"]), inv.final_price - less)
    if "Total Paid" in fields:
        v.eq("details: Total Paid", money(fields["Total Paid"]), paid, tol=ROUND_TOL)
    if "Payment Status" in fields:
        v.contains("details: Payment Status", fields["Payment Status"], status)


def check_details_free(v: Verifier, row: Optional[dict[str, str]], free_qty: float, batch: str) -> None:
    """Free Qty is shown in the Qty column as '<N> pc free' (user-confirmed 2026-10-07);
    a line with no free qty must not show a 'free' label."""
    import re
    if row is None:
        v.true(f"details line [{batch}]: Free Qty shown in the Qty column", False, "line not found")
        return
    qty = row.get("Qty", "")
    if free_qty > 0:
        m = re.search(r"(\d[\d,]*\.?\d*)\s*pc\s*free", qty, re.I)
        v.true(f"details line [{batch}]: Qty column shows '{free_qty:g} pc free'",
               bool(m) and abs(float(m.group(1).replace(",", "")) - free_qty) <= TOL, f"Qty cell {qty!r}")
    else:
        v.true(f"details line [{batch}]: Qty column shows no 'free' label when Free Qty is 0",
               "free" not in qty.lower(), f"Qty cell {qty!r}")


def check_details_item(v: Verifier, row: Optional[dict[str, str]], l: Line, spec, batch: str) -> None:
    tag = f"details line [{batch}] ({l.name})"
    if not v.true(f"{tag}: line found by batch", row is not None, f"no item row contains batch {batch!r}"):
        return
    for col in ("Details", "Batch / Expiry", "Rack No", "Qty", "Qty/Box", "BTP+VAT", "Discount", "Purchase Price",
                "Retail Price", "Wholesale Price", "Margin", "Price"):
        v.true(f"{tag}: column '{col}' present", col in row, "column missing")
    g = row.get
    if g("Details") is not None:
        v.contains(f"{tag}: product", g("Details"), l.name)
    if g("Batch / Expiry") is not None:
        v.contains(f"{tag}: batch", g("Batch / Expiry"), batch)
        if spec.expiry:
            yr = str(spec.expiry[2])
            v.true(f"{tag}: expiry year", yr in g("Batch / Expiry") or yr[2:] in g("Batch / Expiry"), g("Batch / Expiry"))
    if spec.rack:
        v.contains(f"{tag}: rack", (g("Rack No") or "") + " " + (g("Batch / Expiry") or ""), spec.rack)
    if g("Qty") is not None:
        v.any_number(f"{tag}: Qty (boxes / pieces, free included)", g("Qty"),
                     [l.box_qty, l.total_qty, l.total_qty + l.free_qty])
    if g("Qty/Box") is not None:
        v.any_number(f"{tag}: Qty/Box", g("Qty/Box"), [l.qty_per_box])
    if g("BTP+VAT") is not None:
        v.any_number(f"{tag}: BTP+VAT", g("BTP+VAT"), [l.btp_vat_per_box, l.total_btp_vat])
    less_share = l.less_amount or 0
    if g("Discount") is not None and less_share > 0.005:
        shown = numbers_in(g("Discount"))
        v.true(f"{tag}: Discount column shows 'Less Tk <share of Less>' (Less & Buy)",
               "less" in g("Discount").lower() and any(abs(n - less_share) <= 0.02 for n in shown),
               f"cell {g('Discount')!r} expected Less Tk {less_share:.2f}")
    if g("Discount") is not None:
        if less_share > 0.005 and l.special_discount <= 0 and l.discount_value <= 0:
            pass                                    # the cell holds the Less share only (checked above)
        elif l.special_discount > 0:
            v.contains(f"{tag}: Discount column shows 'SP.Dis' for a Special-discount line", g("Discount"), "SP.Dis")
        elif l.discount_value > 0:
            shown = numbers_in(g("Discount"))
            v.true(f"{tag}: Discount shown as % of purchase price (spec 39)",
                   "%" in g("Discount") and any(abs(n - l.discount_pct * 100) <= 0.011 for n in shown),
                   f"cell {g('Discount')!r} expected {l.discount_pct * 100:.4f}% (BUG-INV-021)")
            v.true(f"{tag}: a General-discount line is not labelled 'SP.Dis'", "sp.dis" not in g("Discount").lower(), g("Discount"))
        else:
            v.true(f"{tag}: no discount shown for an ineligible / undiscounted line",
                   not any(n > 0 for n in numbers_in(g("Discount"))) and "sp.dis" not in g("Discount").lower(),
                   f"cell {g('Discount')!r}")
    if g("Purchase Price") is not None and l.purchase_price_pc is not None:
        v.any_number(f"{tag}: Purchase Price per piece / box (spec 40, sheet Q/R)", g("Purchase Price"),
                     purchase_price_candidates(l))
    if g("Retail Price") is not None:
        v.any_number(f"{tag}: Retail Price", g("Retail Price"), [l.retail_per_box])
    if g("Wholesale Price") is not None:
        v.any_number(f"{tag}: Wholesale Price", g("Wholesale Price"), [l.wholesale_per_box])
    if g("Margin") is not None and l.purchase_price_pc is not None:
        if l.retail_margin_pct is not None:
            # the app derives the margin from the per-piece purchase price shown to 2 dp, so allow 0.005 x Qty/Box
            v.any_number(f"{tag}: Retail margin % (sheet S)", g("Margin"), [l.retail_margin_pct * 100],
                         tol=TOL + 0.5 * l.qty_per_box / l.retail_per_box)
            v.any_number(f"{tag}: Retail margin value (sheet T)", g("Margin"), [l.retail_margin_value or 0],
                         tol=TOL + 0.005 * l.qty_per_box)
        if l.wholesale_margin_pct is not None:
            v.any_number(f"{tag}: Wholesale margin % (sheet U)", g("Margin"), [l.wholesale_margin_pct * 100],
                         tol=TOL + 0.5 * l.qty_per_box / l.wholesale_per_box)
            v.any_number(f"{tag}: Wholesale margin value (sheet V)", g("Margin"), [l.wholesale_margin_value or 0],
                         tol=TOL + 0.005 * l.qty_per_box)
    if g("Price") is not None:
        v.any_number(f"{tag}: Price - Total (BTP+VAT x boxes)", g("Price"), [l.total_btp_vat])
        if l.final_line_cost is not None:
            v.any_number(f"{tag}: Price - Final line cost (sheet Y = purchase price x physical qty)", g("Price"),
                         [l.final_line_cost], tol=TOL + 0.005 * (l.total_qty + l.free_qty))
    check_details_free(v, row, l.free_qty, batch)
    if g("Price") is not None:
        v.contains(f"{tag}: Price column labels the line Total (spec 'Total Price')", g("Price"), "Total")
