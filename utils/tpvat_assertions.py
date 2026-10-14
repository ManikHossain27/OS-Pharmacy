"""Screen-level assertions for the TP/VAT inventory journey (counterpart of utils/inventory_assertions.py).

Facts verified live on 2026-10-11 (staging, Manik Pharma):
  cart / checkout rows : Details | Box Qty | TP/Box | VAT/Box | Discount | Total Price | Exp date | Free
                         Discount cell: '-' or 'Tk 20.00 / SP.Dis / 10.00%' (special, % of TP)
  checkout / details   : Total Items | Total Price (TP+VAT) | Total TP | Total VAT | General Discount (on TP) |
                         Special Discount | Round Off | Final Price | Total Paid | Due   (details: + Payment Status)
  details item columns : Details | Batch / Expiry | Rack No | Qty | Qty/Box | TP | VAT | Discount | Purchase Price |
                         Retail Price | Wholesale Price | Margin | Price ('Total:' / 'Final:')
  free pieces          : Qty cell '2 box 20 pc 10 pc free'; VAT is charged on free pieces too (Total = (TP+VAT) x boxes + VAT/pc x free)
"""
from __future__ import annotations

from typing import Optional

from utils.helpers import money, numbers_in
from utils.inventory_assertions import ROUND_TOL, TOL, Verifier, check_details_free
from utils.tpvat_calc import TpVatInventory, TpVatLine


def _free_cell(row: dict[str, str]) -> str:
    txt = row.get("Free", "")
    return txt if any(c.isdigit() for c in txt) else "0"


# --------------------------------------------------------------------------- create form
def check_form_after_entry(v: Verifier, form: dict[str, str], line: TpVatLine) -> None:
    num = lambda k: float((form.get(k) or "0").replace(",", "") or 0)
    v.eq("form: Total Qty = Box Qty x Qty/Box", num("total_qty"), line.box_qty * line.qty_per_box)
    v.eq("form: TP/Box kept as typed", num("tp_per_box"), line.tp_per_box)
    v.eq("form: VAT/Box kept", num("vat_per_box"), line.vat_per_box)


# --------------------------------------------------------------------------- cart
def check_cart(v: Verifier, rows: list[dict[str, str]], lines: list[TpVatLine], cart_total: float,
               total_items: int, specs: Optional[list] = None) -> None:
    v.eq("cart: Total Items", total_items, len(lines))
    v.eq("cart: row count", len(rows), len(lines))
    v.eq("cart: Total Price = sum of (TP + VAT) x boxes (+ VAT on free pcs)", cart_total,
         sum(l.total_price or 0 for l in lines))
    for i, (row, l) in enumerate(zip(rows, lines), 1):
        tag = f"cart row {i} ({l.name})"
        v.contains(f"{tag}: Details shows product", row.get("Details", ""), l.name)
        v.any_number(f"{tag}: Box Qty", row.get("Box Qty", ""), [l.box_qty])
        v.any_number(f"{tag}: TP/Box", row.get("TP/Box", ""), [l.tp_per_box])
        v.any_number(f"{tag}: VAT/Box", row.get("VAT/Box", ""), [l.vat_per_box])
        v.any_number(f"{tag}: Total Price", row.get("Total Price", ""), [l.total_price or 0])
        v.any_number(f"{tag}: Free Qty ('-' means 0)", _free_cell(row), [l.free_qty])
        disc = row.get("Discount", "")
        if l.special_discount > 0:
            v.contains(f"{tag}: Discount cell is labelled SP.Dis", disc, "SP.Dis")
            v.any_number(f"{tag}: Discount cell shows the special value", disc, [l.special_discount])
            if l.total_tp > 0:
                v.any_number(f"{tag}: Discount cell shows the special as % of TP", disc,
                             [l.special_discount / l.total_tp * 100], tol=0.011)
        else:
            v.true(f"{tag}: no discount in the cart before checkout", not any(n > 0 for n in numbers_in(disc))
                   and "sp.dis" not in disc.lower(), f"cell {disc!r}")
        if specs and specs[i - 1].expiry:
            d, mon, y = specs[i - 1].expiry
            v.true(f"{tag}: Exp date shows the chosen expiry", str(y) in row.get("Exp date", "") or mon in row.get("Exp date", ""),
                   f"cell {row.get('Exp date')!r}")


# --------------------------------------------------------------------------- checkout
def check_checkout_summary(v: Verifier, summary: dict[str, float], inv: TpVatInventory, paid: float) -> None:
    raw_final = inv.total_price - inv.total_discount
    v.eq("checkout: Total Price (TP+VAT)", summary["total_price"], inv.total_price)
    if "total_tp" in summary:
        v.eq("checkout: Total TP", summary["total_tp"], inv.total_tp)
        v.eq("checkout: Total VAT (incl. VAT on free pieces)", summary["total_vat"], inv.total_vat)
        v.eq("checkout: Total TP + Total VAT = Total Price", summary["total_tp"] + summary["total_vat"], summary["total_price"])
    v.eq("checkout: General Discount (on TP, eligible lines only, excludes Special)", summary["discount_amount"],
         inv.general_discount)
    v.eq("checkout: Final Price within 0.5 of Total - Discount", summary["final_price"], raw_final, tol=ROUND_TOL)
    v.eq("checkout: Final Price is rounded (sheet K2 = ROUND(Total - Discount))", summary["final_price"], inv.final_price)
    v.true("checkout: Final Price is a whole number", float(summary["final_price"]).is_integer(), f"{summary['final_price']}")
    v.eq("checkout: Round Off equals the sheet round adjustment (K3)", summary["round_off"], inv.round_adjustment)
    v.eq("checkout: Special Discount = sum of per-line specials", summary.get("special_discount", 0), inv.sum_special_applied)
    v.eq("checkout: Total Paid", summary["total_paid"], paid)
    v.eq("checkout: Due", summary["due"], max(inv.final_price - paid, 0), tol=ROUND_TOL)


def check_checkout_rows(v: Verifier, rows: list[dict[str, str]], lines: list[TpVatLine]) -> None:
    v.eq("checkout: item rows", len(rows), len(lines))
    for i, (row, l) in enumerate(zip(rows, lines), 1):
        tag = f"checkout row {i} ({l.name})"
        v.contains(f"{tag}: product", row.get("Details", ""), l.name)
        v.any_number(f"{tag}: Box Qty", row.get("Box Qty", ""), [l.box_qty])
        v.any_number(f"{tag}: TP/Box", row.get("TP/Box", ""), [l.tp_per_box])
        v.any_number(f"{tag}: VAT/Box", row.get("VAT/Box", ""), [l.vat_per_box])
        v.any_number(f"{tag}: Total Price", row.get("Total Price", ""), [l.total_price or 0])


# --------------------------------------------------------------------------- record details
def purchase_price_candidates(l: TpVatLine) -> list[float]:
    """Per-piece AND per-box purchase price, with and without the Round Off share."""
    if l.purchase_price_pc is None:
        return []
    phys = l.total_qty + l.free_qty
    share = (l.round_adj or 0) / phys if phys else 0
    pc = [l.purchase_price_pc, l.purchase_price_pc - share]
    return pc + [p * l.qty_per_box for p in pc]


def check_details_header(v: Verifier, fields: dict[str, str], inv: TpVatInventory, paid: float, status: str,
                         n_lines: int, supplier: Optional[str] = None, mode: str = "TP/VAT", less: float = 0.0) -> None:
    for required in ("Inventory ID", "Inventory Mode", "Supplier Name", "Supplier Phone Number", "Inventory Date & Time",
                     "Received By", "Total Items", "Total Price (TP+VAT)", "Total TP", "Total VAT",
                     "General Discount (on TP)", "Special Discount", "Round Off", "Final Price", "Total Paid",
                     "Payment Status"):
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
    if "Total TP" in fields:
        v.eq("details: Total TP", money(fields["Total TP"]), inv.total_tp)
    if "Total VAT" in fields:
        v.eq("details: Total VAT", money(fields["Total VAT"]), inv.total_vat)
    if "General Discount (on TP)" in fields:
        v.eq("details: General Discount (on TP, excludes Special)", money(fields["General Discount (on TP)"]), inv.general_discount)
    if "Special Discount" in fields:
        v.eq("details: Special Discount = sum of per-line specials", money(fields["Special Discount"]), inv.sum_special_applied)
    if "Round Off" in fields:
        v.eq("details: Round Off = sheet round adjustment", money(fields["Round Off"]), inv.round_adjustment)
    if "Final Price" in fields:
        v.eq("details: Final Price is rounded (sheet K2)" + (" minus Less" if less else ""),
             money(fields["Final Price"]), inv.final_price - less)
    if "Total Paid" in fields:
        v.eq("details: Total Paid", money(fields["Total Paid"]), paid, tol=ROUND_TOL)
    if "Payment Status" in fields:
        v.contains("details: Payment Status", fields["Payment Status"], status)


def check_details_item(v: Verifier, row: Optional[dict[str, str]], l: TpVatLine, spec, batch: str) -> None:
    tag = f"details line [{batch}] ({l.name})"
    if not v.true(f"{tag}: line found by batch", row is not None, f"no item row contains batch {batch!r}"):
        return
    for col in ("Details", "Batch / Expiry", "Rack No", "Qty", "Qty/Box", "TP", "VAT", "Discount", "Purchase Price",
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
    if g("TP") is not None:
        v.any_number(f"{tag}: TP per box / piece", g("TP"), [l.tp_per_box, l.tp_per_box / l.qty_per_box if l.qty_per_box else 0])
    if g("VAT") is not None:
        v.any_number(f"{tag}: VAT per box / piece", g("VAT"),
                     [l.vat_per_box, l.vat_per_box / l.qty_per_box if l.qty_per_box else 0])
    if g("Discount") is not None:
        if l.special_discount > 0:
            v.contains(f"{tag}: Discount column shows 'SP.Dis' for a Special-discount line", g("Discount"), "SP.Dis")
        elif l.discount_value > 0:
            shown = numbers_in(g("Discount"))
            v.true(f"{tag}: Discount shown as % of TP (spec 39)",
                   "%" in g("Discount") and any(abs(n - l.discount_pct * 100) <= 0.011 for n in shown),
                   f"cell {g('Discount')!r} expected {l.discount_pct * 100:.4f}%")
            v.true(f"{tag}: a General-discount line is not labelled 'SP.Dis'", "sp.dis" not in g("Discount").lower(), g("Discount"))
        else:
            v.true(f"{tag}: no discount shown for an ineligible / undiscounted line",
                   not any(n > 0 for n in numbers_in(g("Discount"))) and "sp.dis" not in g("Discount").lower(),
                   f"cell {g('Discount')!r}")
    if g("Purchase Price") is not None and l.purchase_price_pc is not None:
        v.any_number(f"{tag}: Purchase Price per piece / box (spec 40, sheet T/U)", g("Purchase Price"),
                     purchase_price_candidates(l), tol=TOL + 0.005 * l.qty_per_box)
    if g("Retail Price") is not None:
        v.any_number(f"{tag}: Retail Price", g("Retail Price"), [l.retail_per_box])
    if g("Wholesale Price") is not None:
        v.any_number(f"{tag}: Wholesale Price", g("Wholesale Price"), [l.wholesale_per_box])
    if g("Margin") is not None and l.purchase_price_pc is not None:
        extra = 0.005 * l.qty_per_box        # the app derives margin from the per-piece price shown to 2 dp
        if l.retail_margin_pct is not None:
            v.any_number(f"{tag}: Retail margin % (sheet V)", g("Margin"), [l.retail_margin_pct * 100],
                         tol=TOL + 0.5 * l.qty_per_box / max(l.retail_per_box, 1e-9))
            v.any_number(f"{tag}: Retail margin value (sheet W)", g("Margin"), [l.retail_margin_value or 0], tol=TOL + extra)
        if l.wholesale_margin_pct is not None:
            v.any_number(f"{tag}: Wholesale margin % (sheet X)", g("Margin"), [l.wholesale_margin_pct * 100],
                         tol=TOL + 0.5 * l.qty_per_box / max(l.wholesale_per_box, 1e-9))
            v.any_number(f"{tag}: Wholesale margin value (sheet Y)", g("Margin"), [l.wholesale_margin_value or 0], tol=TOL + extra)
    if g("Price") is not None:
        v.any_number(f"{tag}: Price - Total (TP+VAT incl. VAT on free pcs)", g("Price"), [l.total_price or 0])
        v.contains(f"{tag}: Price column labels the line Total", g("Price"), "Total")
        if l.final_line_cost is not None:
            v.any_number(f"{tag}: Price - Final line cost (sheet AB = purchase price x physical qty)", g("Price"),
                         [l.final_line_cost], tol=TOL + 0.005 * (l.total_qty + l.free_qty))
    check_details_free(v, row, l.free_qty, batch)
