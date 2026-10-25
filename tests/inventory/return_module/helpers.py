"""Helpers shared by the Inventory Return test modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from pages.inventory_return_page import InventoryReturnPage, InventoryReturnRecordPage
from pages.my_products_page import MyProductsPage
from pages.supplier_list_page import SupplierListPage
from utils.inventory_calc import excel_round

TOL = 0.011


def expected_summary(total: float, demurrage=None) -> dict:
    """Return Checkout figures for a cart worth ``total``: demurrage (value, '%'|'Tk'), Round Off and Final Price."""
    value, unit = demurrage if demurrage else (0, "%")
    dem = Decimal(str(total)) * Decimal(str(value)) / 100 if unit == "%" else Decimal(str(value))
    dem = float(dem.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    final = float(excel_round(total - dem))
    return {"demurrage": dem, "final_price": final, "round_off": round(final - (total - dem), 2)}


def supplier_balance(page, name: str) -> float:
    """The supplier's signed balance (+ Due, - Advance) on the Supplier List."""
    return SupplierListPage(page).open().balance(name)


def batch_stock(ret: InventoryReturnPage, product: str, batch: str) -> float | None:
    """Pieces the Inventory Return form offers for ``batch`` (None once the batch has no stock left)."""
    ret.select_product(product)
    for b in ret.batch_options():
        if b["batch"] == batch:
            return b["pcs"]
    return None


def product_stock(page, name: str) -> tuple[float, float]:
    """(pieces, boxes) the Product List's Stock Status column shows for ``name`` ('86727 pcs 8,672.7 box')."""
    import re
    mp = MyProductsPage(page).open().wait_loaded()
    mp.search(name)
    page.wait_for_timeout(2500)
    text = mp.row_cells(name)["Stock Status"]
    nums = [float(n.replace(",", "")) for n in re.findall(r"-?[\d,]+(?:\.\d+)?", text)]
    assert len(nums) >= 2, f"unexpected Stock Status {text!r}"
    return nums[0], nums[1]


@dataclass
class Done:
    status: int | None
    body: str
    toast: str
    cart_total: float
    summary: dict
    lines: list = field(default_factory=list)
    supplier: str = ""


def checkout_and_complete(ret: InventoryReturnPage, supplier: str, demurrage=None, *, invoice: str = "", note: str = "") -> Done:
    """From a filled cart: open the checkout, pick ``supplier``, apply ``demurrage`` (value, unit), Complete."""
    lines = ret.cart_lines()
    total = ret.cart_total()
    ret.go_to_checkout()
    ret.select_supplier(supplier)
    if demurrage:
        ret.set_demurrage(*demurrage)
    if invoice:
        ret.set_invoice(invoice)
    if note:
        ret.set_note(note)
    summary = ret.summary()
    status, body = ret.complete()
    return Done(status, body, ret.toast_text(), total, summary, lines, supplier)


def latest_return(page, expect_supplier: str | None = None) -> dict:
    """The newest row of the Inventory Return Record."""
    rec = InventoryReturnRecordPage(page).open()
    row = rec.first_row()
    if expect_supplier:
        assert row["supplier"].lower().startswith(expect_supplier.lower()[:8]), row
    return row


def detail(text: str, label: str) -> str:
    """The value that follows ``label`` in the Return Details dialog text ('' when absent)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if l == label or l.startswith(label):
            return lines[i + 1] if i + 1 < len(lines) else ""
    return ""
