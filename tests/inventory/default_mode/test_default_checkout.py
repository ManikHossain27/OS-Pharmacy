"""Default mode - Inventory Checkout (spec sections 35-41).

Cart shape x discount (40 combinations) is verified against the oracle WITHOUT
completing the inventory, so this module creates no stock or financial data.
"""
from __future__ import annotations

import allure
import pytest

from tests.inventory.scenario_params import scenario_params
from tests.inventory.shared_checkout import CheckoutBehaviourCases
from utils.inventory_calc import build
from utils.inventory_assertions import Verifier, check_checkout_rows, check_checkout_summary
from utils.inventory_scenarios import CART_SHAPES, Scenario, e2e_scenarios

pytestmark = [pytest.mark.inventory, pytest.mark.regression]


@allure.epic("Inventory")
@allure.feature("Default mode - checkout")
class TestSupplierRequired:
    """Runs FIRST in this module: the app keeps the last chosen supplier across navigation and reloads
    (no clear control), so 'no supplier selected' only exists until a supplier is picked for the first time."""

    @allure.story("Complete Inventory is disabled until a supplier is selected (spec 44.1)")
    @pytest.mark.negative
    def test_complete_requires_supplier(self, flow):
        flow.fill_cart(Scenario("s", CART_SHAPES["single_plain"]))
        co = flow.inventory.go_to_checkout()
        if co.supplier_selected():
            pytest.skip("a supplier is already selected - the app persists the last supplier across reloads and "
                        "offers no way to clear it, so 'no supplier' cannot be set up in this session")
        assert not co.complete_enabled(), "Complete Inventory enabled with no supplier selected"
        co.select_first_supplier()
        assert co.complete_enabled()


@allure.epic("Inventory")
@allure.feature("Default mode - checkout")
class TestCheckoutMatrix:

    @pytest.mark.parametrize("scenario", scenario_params(e2e_scenarios()))
    @allure.story("Checkout Total / Discount / Final Price and item rows match the oracle for every cart x discount")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_checkout_summary_matches_oracle(self, flow, scenario):
        for bug in scenario.known_bugs:
            allure.dynamic.issue(bug)
        j = flow.fill_cart(scenario)
        inv = flow.oracle(j)
        co = flow.open_checkout(j)
        v = Verifier(f"checkout [{scenario.id}]")
        check_checkout_rows(v, co.cart_rows(), j.lines)
        check_checkout_summary(v, co.summary(), inv, paid=inv.final_price)   # app pre-fills Total Paid = Final Price
        v.assert_all()


@allure.epic("Inventory")
@allure.feature("Default mode - checkout")
class TestCheckoutBehaviour(CheckoutBehaviourCases):
    MODE = "Default"
    SHAPES = CART_SHAPES
    build = staticmethod(build)

    @allure.story("Add New Supplier is offered from checkout (spec 44.1)")
    def test_add_new_supplier_link(self, flow):
        flow.fill_cart(Scenario("s", CART_SHAPES["single_plain"]))
        co = flow.inventory.go_to_checkout()
        assert co.add_new_supplier_link.count() > 0

    @pytest.mark.parametrize("inv_type,label", [("Purchase", "Purchase"), ("Borrow", "Borrowed")])
    @allure.story("Inventory Type supports Purchase and Borrow (spec 44.1; the UI labels Borrow as 'Borrowed')")
    def test_inventory_types(self, flow, inv_type, label):
        flow.fill_cart(Scenario("s", CART_SHAPES["single_plain"]))
        co = flow.inventory.go_to_checkout()
        assert set(co.inventory_type_options()) >= {"Purchase", "Borrowed"}
        co.select_inventory_type(inv_type)
        assert co.inventory_type() == label

    @allure.story("Invoice number is accepted")
    def test_invoice_number(self, flow):
        j, co = self._open(flow, "single_plain")
        co.set_invoice_number("INV-QA-0001")
        assert co.invoice_number_input.input_value() == "INV-QA-0001"
