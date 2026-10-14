"""The end-to-end journey shared by the three inventory modes (spec sections 35-44.1).

``journey`` runs create -> cart -> checkout -> complete -> Inventory Details and ``buy_journey`` the same with a Total
Paid that differs from the Final Price (Due & Buy / Less & Buy / Advance & Buy).  Both verify EVERY stage against the
mode's oracle and return the stage verifiers; ``assert_journey`` reports them together so a mismatch at one stage never
hides another.  The mode (``flow.mode``) selects its assertion helpers: TP/VAT has its own cart / checkout / details
checks, Default and Opening Stock share one set.
"""
from __future__ import annotations

import allure

from pages.inventory_record_page import InventoryRecordPage
from utils import inventory_assertions, tpvat_assertions
from utils.inventory_assertions import Verifier
from utils.inventory_calc import excel_round
from utils.inventory_scenarios import Scenario


def _checks(flow):
    """The module holding the mode's cart / checkout / details assertion helpers."""
    return tpvat_assertions if flow.mode == "TP/VAT" else inventory_assertions


def _totals(flow, co) -> dict:
    """The checkout summary as the mode exposes it."""
    return co.tpvat_totals() if flow.mode == "TP/VAT" else co.summary()


def journey(flow, scenario: Scenario, *, paid_ratio: float | None = 1.0, paid_abs: float | None = None):
    """Run create -> cart -> checkout -> complete -> details, verifying each stage.
    Returns (journey, verifiers)."""
    ck = _checks(flow)
    inv_page = flow.inventory
    j = flow.fill_cart(scenario)
    oracle = flow.oracle(j)
    verifiers: list[Verifier] = []

    v_cart = Verifier("2. cart")
    ck.check_cart(v_cart, inv_page.cart_rows(), j.lines, inv_page.cart_total_price(), inv_page.total_items(), j.specs)
    verifiers.append(v_cart)

    co = flow.open_checkout(j)
    oracle = flow.oracle(j)                      # the discount may have been blocked (input disabled)
    paid = paid_abs if paid_abs is not None else round(oracle.final_price * (paid_ratio or 0), 2)
    flow.pay(co, j, paid)
    oracle = flow.oracle(j, paid)
    v_co = Verifier("3. checkout")
    ck.check_checkout_rows(v_co, co.cart_rows(), j.lines)
    ck.check_checkout_summary(v_co, _totals(flow, co), oracle, paid)
    verifiers.append(v_co)

    j.status = "Paid" if paid + 0.51 >= oracle.final_price else ("Partial" if paid > 0 else "Due")
    dlg = flow.complete_and_open_details(co, j)

    v_rec = Verifier("4. inventory details")
    fields = dlg.pricing_breakdown()
    ck.check_details_header(v_rec, fields, oracle, paid, "Paid" if j.status == "Paid" else "Due",
                            len(j.lines), j.supplier, mode=flow.mode)
    items = dlg.item_rows()
    v_rec.eq("details: item row count", len(items), len(j.lines))
    for line, spec, batch in zip(j.lines, j.specs, j.batches):
        ck.check_details_item(v_rec, dlg.item_row_by_batch(batch), line, spec, batch)
    verifiers.append(v_rec)
    return j, verifiers


def assert_journey(verifiers: list[Verifier]) -> None:
    failures = []
    for v in verifiers:
        v.attach()
        failures += [f"[{v.stage}] {l}: {d}" for l, _, d in v.failures]
    assert not failures, f"{len(failures)} check(s) failed across the journey:\n  - " + "\n  - ".join(failures)


def expected_dialog_options(kind: str) -> list[str]:
    return ["Due & Buy", "Less & Buy"] if kind == "less" else ["Advance & Buy"]


def check_payment_dialog(v: Verifier, snap: dict, final: float, paid: float, supplier: str) -> None:
    """The 'You paid less/more than the bill' dialog against the figures typed in checkout."""
    gap = round(final - paid, 2)
    kind = "less" if gap > 0 else "more"
    v.eq("dialog: kind (less / more)", snap.get("kind"), kind)
    v.eq("dialog: BILL = Final Price", snap.get("bill"), final, tol=0.011)
    v.eq("dialog: YOU PAID = Total Paid", snap.get("paid"), paid, tol=0.011)
    v.eq(f"dialog: {'SHORT BY' if kind == 'less' else 'EXTRA'} = |Final Price - Paid|", snap.get("gap"), abs(gap), tol=0.011)
    v.eq("dialog: offered options", sorted(snap.get("options") or []), sorted(expected_dialog_options(kind)))
    text = snap.get("text", "")
    amount = f"{abs(gap):,.2f}"
    if kind == "less":
        v.contains("dialog: Due option states the due amount", text, f"Due: Tk {amount}")
        v.contains("dialog: Due option says it is owed to the supplier", text, f"will be Due to {supplier}")
        v.contains("dialog: Less option states the waived amount", text, f"Less: Tk {amount}")
        v.contains("dialog: Less option says it is not paid", text, f"You do not pay the Tk {amount}")
    else:
        v.contains("dialog: Advance option states the extra amount", text, f"Advance: Tk {amount}")
        v.contains("dialog: Advance option says it is held by the supplier", text, f"will be Advance with {supplier}")


def buy_journey(flow, scenario: Scenario, *, choice: str, paid_ratio: float | None = None, paid_delta: float | None = None):
    """Create an inventory whose Total Paid differs from the Final Price, take ``choice`` in the
    payment dialog and verify: the dialog, the record's Details and the supplier's balance after.

    Supplier balance (workbook M2..M5, signed: + we owe the supplier / - advance):
        after = before + Final - Paid - Less           Due & Buy: Less = 0
                                                       Less & Buy: Less = Final - Paid  (so after == before)
                                                       Advance & Buy: Less = 0, Paid > Final
    """
    ck = _checks(flow)
    supplier, before = flow.supplier_balance()
    supplier = supplier.splitlines()[0].strip()
    flow.inventory.open(flow.mode)                         # back to the Inventory form of this flow's mode
    j = flow.fill_cart(scenario)
    j.balance_before = before
    base = flow.oracle(j)
    co = flow.open_checkout(j)
    final = base.final_price
    typed = final * paid_ratio if paid_ratio is not None else final + paid_delta
    paid = float(excel_round(typed))     # the app rounds a typed fraction to a whole taka (112.7 -> 113, 67.5 -> 68)
    flow.pay(co, j, typed)
    j.paid = paid
    j.less = round(final - paid, 2) if choice == "Less & Buy" else 0.0
    oracle = flow.oracle(j, paid, j.less)
    verifiers: list[Verifier] = []

    v_co = Verifier("3. checkout")
    ck.check_checkout_rows(v_co, co.cart_rows(), j.lines)
    # the checkout field keeps the typed amount; the rounding to a whole taka happens when Complete is pressed
    ck.check_checkout_summary(v_co, _totals(flow, co), oracle, typed)
    verifiers.append(v_co)

    j.choice = choice
    dlg = flow.complete_and_open_details(co, j, choice=choice)
    v_dlg = Verifier("3b. payment dialog")
    snap = co.last_payment_dialog or {}
    v_dlg.true("dialog: shown after Complete Inventory", bool(snap), "no payment dialog was captured")
    if snap:
        check_payment_dialog(v_dlg, snap, final, paid, supplier)
    verifiers.append(v_dlg)

    v_rec = Verifier("4. inventory details")
    fields = dlg.pricing_breakdown()
    allure.attach(dlg.page_text(), name="Inventory Details page text", attachment_type=allure.attachment_type.TEXT)
    invoice_due = max(final - paid - j.less, 0)
    invoice_adv = max(paid - final, 0)
    # Payment Status the app uses: Less & Buy settles the bill -> "Paid"; Advance & Buy -> "Advance".
    # Due & Buy: the invoice is NOT paid (spec 44.1: lower payment is recorded as Due).
    expected_status = {"Due & Buy": "", "Less & Buy": "Paid", "Advance & Buy": "Advance"}[choice]
    ck.check_details_header(v_rec, fields, oracle, paid, expected_status, len(j.lines), j.supplier, mode=flow.mode,
                            less=j.less)
    status = (fields.get("Payment Status") or "").lower()
    if choice == "Due & Buy":
        v_rec.true("details: Due & Buy leaves the invoice due (BUG-INV-031: status must not read Advance/Paid)",
                   "due" in status or "partial" in status,
                   f"Payment Status {fields.get('Payment Status')!r}")
    due_shown = dlg.labelled_amount("Due", "Due Amount", "Due Balance")
    if due_shown is not None:
        v_rec.eq("details: Due shown = Final - Paid - Less", due_shown, invoice_due, tol=0.51)
    less_shown = dlg.labelled_amount("Less", "Less Amount")
    if choice == "Less & Buy" and j.less > 0:
        v_rec.true("details: pricing breakdown has a 'Less' row so Total - discounts - Less + Round Off = Final",
                   less_shown is not None, "no 'Less' label in the pricing breakdown")
    if less_shown is not None:
        v_rec.eq("details: Less shown = amount waived by Less & Buy", less_shown, j.less, tol=0.51)
    adv_shown = dlg.labelled_amount("Advance", "Advance Amount")
    if adv_shown is not None:
        v_rec.eq("details: Advance shown = Paid - Final", adv_shown, invoice_adv, tol=0.51)
    items = dlg.item_rows()
    v_rec.eq("details: item row count", len(items), len(j.lines))
    for line, spec, batch in zip(j.lines, j.specs, j.batches):
        ck.check_details_item(v_rec, dlg.item_row_by_batch(batch), line, spec, batch)
    verifiers.append(v_rec)

    if choice == "Due & Buy":
        v_list = Verifier("4b. record list row")
        rec_row = InventoryRecordPage(flow.page).open().row(0)
        status_text = InventoryRecordPage(flow.page).status_cell_text(rec_row)
        v_list.contains("record list: status says Due (BUG-INV-031)", status_text, "Due")
        v_list.any_number("record list: Due = this record's own Final - Paid, not netted against the supplier's advance (BUG-INV-031)",
                          status_text, [invoice_due], tol=0.51)
        verifiers.append(v_list)

    # ---- supplier balance after the purchase
    _, after = flow.supplier_balance(supplier)
    j.balance_after = after
    v_bal = Verifier("5. supplier balance")
    expected = round(before + final - paid - j.less, 2)
    v_bal.eq(f"supplier balance after {choice} = before ({before:+,.2f}) + Final ({final:,.2f}) - Paid ({paid:,.2f}) - Less ({j.less:,.2f})",
             after, expected, tol=0.51)
    if choice == "Less & Buy":
        v_bal.eq("Less & Buy: the owner does not pay the waived amount, so the balance does not move", after, before, tol=0.51)
    verifiers.append(v_bal)
    return j, verifiers
