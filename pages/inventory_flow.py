"""Business-flow facade over the Inventory page objects.

Keeps multi-page journeys (fill cart -> checkout -> complete -> open the new
record's details) out of the tests, so tests read as intent + verification.
No locators live here - everything goes through the page objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import allure

from pages.inventory_checkout_page import InventoryCheckoutPage
from pages.inventory_page import InventoryPage
from pages.inventory_record_page import InventoryDetailsDialog, InventoryRecordPage
from pages.supplier_list_page import SupplierListPage
from utils.inventory_calc import Inventory, Line, build
from utils.inventory_scenarios import LineSpec, Scenario


@dataclass
class Journey:
    scenario: Scenario
    specs: list[LineSpec]
    batches: list[str]
    lines: list[Line] = field(default_factory=list)       # oracle lines, values read back from the FORM
    inventory: Optional[Inventory] = None                 # oracle totals for this cart + discount
    paid: float = 0.0
    supplier: str = ""
    status: str = "Paid"
    details: Optional[InventoryDetailsDialog] = None
    discount_blocked: bool = False      # discount input disabled (no eligible line)
    choice: Optional[str] = None        # payment-decision button: "Due & Buy" | "Less & Buy" | "Advance & Buy"
    less: float = 0.0                   # amount waived by "Less & Buy" (workbook M5)
    balance_before: Optional[float] = None   # supplier balance before completing (signed: + due, - advance)
    balance_after: Optional[float] = None


class InventoryFlow:
    mode = "Default"   # Inventory Mode this flow drives (route + radio label)
    _seq = 0          # CLASS-level: one counter for the whole run, because the backend rejects a batch no
                      # already used by ANY other batch ("Batch no '...' is already used by another batch")

    def __init__(self, inventory: InventoryPage, run_tag: str):
        self.inventory = inventory
        self.page = inventory.page
        self.run_tag = run_tag

    # ------------------------------------------------------------------ cart
    def next_batch(self, label: str = "L") -> str:
        InventoryFlow._seq += 1
        return f"QA_{self.run_tag}_{label}{InventoryFlow._seq}"

    def fill_cart(self, scenario: Scenario) -> Journey:
        with allure.step(f"Fill the cart for scenario {scenario.id}"):
            j = Journey(scenario=scenario, specs=list(scenario.lines),
                        batches=[s.batch or self.next_batch() for s in scenario.lines])
            for spec, batch in zip(j.specs, j.batches):
                j.lines.append(self.inventory.add_line(spec, batch))
            return j

    def oracle(self, j: Journey, paid: Optional[float] = None, less: Optional[float] = None) -> Inventory:
        pct = flat = 0.0
        if j.scenario.discount:
            value, unit = j.scenario.discount
            pct, flat = (value, 0.0) if unit == "%" else (0.0, value)
        for l in j.lines:                      # build() recomputes derived fields in place
            l.special_discount = 0
        j.inventory = build(j.lines, pct=pct, flat=flat, paid=paid or 0.0,
                            supplier_balance=j.balance_before or 0.0,
                            less=j.less if less is None else less)
        return j.inventory

    # ------------------------------------------------------------------ checkout
    @allure.step("Go to checkout and configure supplier / discount / payment")
    def open_checkout(self, j: Journey) -> InventoryCheckoutPage:
        co = self.inventory.go_to_checkout()
        if j.scenario.inventory_type != "Purchase":
            co.select_inventory_type(j.scenario.inventory_type)
        j.supplier = co.select_first_supplier().splitlines()[0].strip()
        if not j.scenario.discount:
            co.reset_discount()
        if j.scenario.discount:
            if co.discount_enabled():
                co.set_discount(*j.scenario.discount)
            else:
                j.discount_blocked = True   # spec 38: every line has Free Qty -> nothing to discount
        return co

    def pay(self, co: InventoryCheckoutPage, j: Journey, paid: float) -> None:
        j.paid = paid
        if paid > 0:
            co.set_payment_method(j.scenario.payment_method)
        co.set_paid_amount(paid)

    # ------------------------------------------------------------------ supplier balance
    @allure.step("Read the supplier's balance on the Supplier List")
    def supplier_balance(self, name: Optional[str] = None) -> tuple[str, float]:
        """(supplier name, signed balance) - + = the pharmacy owes the supplier, - = the supplier holds an advance."""
        page = SupplierListPage(self.page).open()
        name = name or page.first_supplier()
        return name, page.balance(name)

    def default_choice(self, j: Journey, final_price: float) -> Optional[str]:
        """Which payment-decision button a journey takes when the test did not name one."""
        if j.paid + 0.005 < final_price:
            return InventoryCheckoutPage.DUE_BUY
        if j.paid > final_price + 0.005:
            return InventoryCheckoutPage.ADVANCE_BUY
        return None

    # ------------------------------------------------------------------ completion
    @allure.step("Complete the inventory and open its Inventory Details")
    def complete_and_open_details(self, co: InventoryCheckoutPage, j: Journey,
                                  choice: Optional[str] = None) -> InventoryDetailsDialog:
        choice = choice or j.choice
        if choice is None and j.inventory is not None:
            choice = self.default_choice(j, j.inventory.final_price)
        j.choice = choice
        status, body = co.complete_capturing_response(settle_ms=30_000, choice=choice)
        if status is None or status >= 400:
            raise AssertionError(f"Complete Inventory did not create the inventory: create-response status={status} "
                                 f"body={body[:300]!r} choice={choice!r} (see BUG-INV-011/020 - the UI shows no error)")
        record = InventoryRecordPage(self.page).open()
        j.details = record.open_details(0)
        return j.details


class TpVatFlow(InventoryFlow):
    """TP/VAT counterpart of ``InventoryFlow``: lines go in through TP/Box + VAT/Box and the oracle is
    ``utils.tpvat_calc`` (sheet 'TP per vat mode (2)'). Checkout / payment / completion are shared."""
    mode = "TP/VAT"

    def fill_cart(self, scenario: Scenario) -> Journey:
        with allure.step(f"Fill the TP/VAT cart for scenario {scenario.id}"):
            j = Journey(scenario=scenario, specs=list(scenario.lines),
                        batches=[s.batch or self.next_batch("T") for s in scenario.lines])
            for spec, batch in zip(j.specs, j.batches):
                j.lines.append(self.inventory.add_tpvat_line(spec, batch))
            return j

    def oracle(self, j: Journey, paid: Optional[float] = None, less: Optional[float] = None):
        from utils.tpvat_calc import build as build_tpvat
        pct = flat = 0.0
        if j.scenario.discount and not j.discount_blocked:
            value, unit = j.scenario.discount
            pct, flat = (value, 0.0) if unit == "%" else (0.0, value)
        less_value = j.less if less is None else less
        # "Less" follows the application's Default-mode rule (share of the TOTAL price, spread over D+E); the TP/VAT sheet's
        # own col Z / M3 are a workbook gap (TPVAT-1) and are only reproduced by tools/validate_tpvat_oracle.py.
        j.inventory = build_tpvat(j.lines, pct=pct, flat=flat, paid=paid or 0.0,
                                  supplier_balance=j.balance_before or 0.0, less=less_value,
                                  less_rule="total" if less_value else "sheet")
        return j.inventory


class OpeningStockFlow(InventoryFlow):
    """Opening Stock counterpart of ``InventoryFlow``: BTP + VAT/Box is derived from Retail Price/Box and the
    Opening Stock % (sheet 'Opening Stock'), everything after that is the Default-mode calculation, so the
    oracle is ``utils.inventory_calc`` fed with the form's own values and checkout / payment / completion are shared."""
    mode = "Opening Stock"

    def fill_cart(self, scenario: Scenario) -> Journey:
        with allure.step(f"Fill the Opening Stock cart for scenario {scenario.id}"):
            j = Journey(scenario=scenario, specs=list(scenario.lines),
                        batches=[s.batch or self.next_batch("O") for s in scenario.lines])
            for spec, batch in zip(j.specs, j.batches):
                j.lines.append(self.inventory.add_opening_line(spec, batch))
            return j

    def oracle(self, j: Journey, paid: Optional[float] = None, less: Optional[float] = None) -> Inventory:
        pct = flat = 0.0
        if j.scenario.discount and not j.discount_blocked:
            value, unit = j.scenario.discount
            pct, flat = (value, 0.0) if unit == "%" else (0.0, value)
        j.inventory = build(j.lines, pct=pct, flat=flat, paid=paid or 0.0,
                            supplier_balance=j.balance_before or 0.0,
                            less=j.less if less is None else less)
        return j.inventory
