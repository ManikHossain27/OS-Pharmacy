"""Inventory - behaviour ACROSS the three modes (spec sections 3, 29, 33-34, 'modes stay independent').

Drawer state, cart contents, form fields and cart columns are per mode; a held inventory keeps its mode, its lines and
every entered detail.  Only the last journey creates real data (one Default-mode inventory is completed from a held
cart to prove the Hold List is cleaned up).
"""
from __future__ import annotations

import itertools

import allure
import pytest

from tests.inventory.cross_mode.conftest import MODES
from utils.constants import INVENTORY_FIELDS_BY_MODE

pytestmark = [pytest.mark.inventory, pytest.mark.regression]


def _headers(inv) -> list[str]:
    return [h.strip() for h in inv.cart.headers() if h and h.strip()]


@allure.epic("Inventory")
@allure.feature("Cross-mode - Add Items drawer state (spec 3)")
class TestDrawerState:

    @pytest.mark.parametrize("mode", MODES)
    @allure.story("Changing the mode opens the Add Items to Cart drawer for that mode")
    def test_drawer_open_on_mode_change(self, modes, mode):
        inv = modes.go(mode)
        assert inv.panel_open(), f"drawer is closed after switching to {mode}"

    @pytest.mark.parametrize("closed,other", list(itertools.permutations(MODES, 2)),
                             ids=[f"close_{a}_see_{b}".replace("/", "").replace(" ", "") for a, b in itertools.permutations(MODES, 2)])
    @allure.story("Closing the drawer in one mode does not close it in another, and is remembered for the first")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_drawer_state_is_per_mode(self, modes, closed, other):
        inv = modes.go(closed)
        inv.close_add_items_panel()
        assert not inv.panel_open()
        modes.go(other)
        assert inv.panel_open(), f"closing the drawer in {closed} also closed it in {other}"
        modes.go(closed)
        assert not inv.panel_open(), f"{closed} forgot that its drawer was closed"

    @allure.story("A drawer closed in two modes leaves the third mode's drawer open")
    def test_third_mode_stays_open(self, modes):
        for m in ("Default", "TP/VAT"):
            modes.go(m).close_add_items_panel()
        assert modes.go("Opening Stock").panel_open()
        assert not modes.go("Default").panel_open() and not modes.go("TP/VAT").panel_open()

    @pytest.mark.parametrize("mode", MODES)
    @allure.story("A closed drawer can be reopened in its own mode")
    def test_reopen_drawer(self, modes, mode):
        inv = modes.go(mode)
        inv.close_add_items_panel()
        inv.open_add_items_panel()
        assert inv.panel_open()


@allure.epic("Inventory")
@allure.feature("Cross-mode - form fields and cart columns follow the mode (spec 3 / 29)")
class TestModeSpecificUi:

    @pytest.mark.parametrize("mode", MODES)
    @allure.story("Every mode shows its own field set (TP/Box + VAT/Box, BTP+VAT, Opening Stock %)")
    def test_form_fields_per_mode(self, modes, mode):
        inv = modes.go(mode)
        inv.open_add_items_panel()
        for key, fid in INVENTORY_FIELDS_BY_MODE[mode].items():
            assert inv.page.locator(f"#{fid}").count() == 1, f"{mode}: field {key!r} (#{fid}) missing"
        others = set().union(*(set(v.values()) for k, v in INVENTORY_FIELDS_BY_MODE.items() if k != mode)) \
            - set(INVENTORY_FIELDS_BY_MODE[mode].values())
        for fid in others:
            assert inv.page.locator(f"#{fid}").count() == 0, f"{mode}: foreign field #{fid} is shown"

    @pytest.mark.parametrize("mode", MODES)
    @allure.story("The cart's purchase columns adapt to the mode")
    def test_cart_columns_per_mode(self, modes, mode):
        modes.fill(mode, "single_plain")
        h = _headers(modes.inv)
        if mode == "Default":
            assert "BTP+VAT" in h and "TP/Box" not in h and "VAT/Box" not in h, h
        elif mode == "TP/VAT":
            assert "TP/Box" in h and "VAT/Box" in h and "BTP+VAT" not in h, h
        else:
            assert "BTP+VAT/Box" in h and "TP/Box" not in h, h


@allure.epic("Inventory")
@allure.feature("Cross-mode - cart isolation")
class TestCartIsolation:

    @allure.story("Each mode has its own cart: lines added in one mode never show in another")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_carts_are_independent(self, modes):
        totals = {}
        for mode, shape in (("Default", "single_plain"), ("TP/VAT", "two_plain"),
                            ("Opening Stock", "three_plain_free_plain")):
            modes.fill(mode, shape)
            totals[mode] = (modes.inv.total_items(), modes.inv.cart_total_price())
        assert [totals[m][0] for m in MODES] == [1, 2, 3], totals
        for mode in MODES:           # come back to each: untouched
            modes.go(mode)
            assert (modes.inv.total_items(), modes.inv.cart_total_price()) == totals[mode], \
                f"{mode} cart changed while other modes were edited"

    @allure.story("The one-line-per-product rule is per cart: the same product may sit in each mode's cart")
    def test_same_product_in_every_mode(self, modes):
        for mode in MODES:
            modes.fill(mode, "single_plain")      # every shape's first line is P0
            assert modes.inv.total_items() == 1
        for mode in MODES:
            assert modes.go(mode).total_items() == 1

    @allure.story("Deleting a line in one mode leaves the other modes' carts alone")
    def test_delete_in_one_mode(self, modes):
        for mode in MODES:
            modes.fill(mode, "single_plain")
        inv = modes.go("TP/VAT")
        inv.delete_cart_row(inv.cart_row(0))
        assert inv.total_items() == 0
        assert modes.go("Default").total_items() == 1 and modes.go("Opening Stock").total_items() == 1

    @allure.story("Switching mode with an unsaved form entry does not add anything to a cart")
    def test_switch_with_unsaved_form(self, modes):
        inv = modes.go("Default")
        inv.select_product(inv.resolve_product("P0"), exact=True)
        inv.set_value("box_qty", 4)
        modes.go("TP/VAT")
        assert inv.total_items() == 0
        assert modes.go("Default").total_items() == 0


@allure.epic("Inventory")
@allure.feature("Cross-mode - expanded cart view (spec 29)")
class TestExpandedCart:

    @pytest.mark.parametrize("mode", MODES)
    @allure.story("Closing the drawer expands the cart: current stock (pcs + boxes), Sale Price (Retail + Wholesale), Storage")
    def test_expanded_cart_columns(self, modes, mode):
        j = modes.fill(mode, "single_plain")
        inv = modes.inv
        compact = [h.lower() for h in _headers(inv)]
        inv.close_add_items_panel()
        inv.page.wait_for_timeout(500)
        expanded = [h.lower() for h in _headers(inv)]
        missing = [w for w in ("c. stock", "pcs/box", "sale price", "storage") if w not in expanded]
        assert not missing, f"{mode}: expanded cart lacks {missing}; compact={compact} expanded={expanded}"
        assert not {"c. stock", "sale price", "storage"} & set(compact), f"compact cart already shows {compact}"
        row = inv.cart_rows()[0]
        spec = j.specs[0]
        cell = next(v for k, v in row.items() if k.lower() == "sale price")
        from utils.helpers import numbers_in
        nums = numbers_in(cell)
        assert spec.retail in nums and spec.wholesale in nums, f"Sale Price cell {cell!r} lacks Retail {spec.retail} / Wholesale {spec.wholesale}"
        assert spec.rack in next(v for k, v in row.items() if k.lower() == "storage"), row


@allure.epic("Inventory")
@allure.feature("Cross-mode - Hold / Resume (spec 33-34)")
class TestHoldAcrossModes:

    @pytest.mark.parametrize("mode", MODES)
    @allure.story("Hold keeps every entered detail; Resume restores the same cart rows in the same mode")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_hold_resume_restores_cart(self, modes, mode):
        modes.fill(mode, "three_plain_free_plain")
        inv = modes.inv
        before_rows, before_total, before_n = inv.cart_rows(), inv.cart_total_price(), inv.total_items()
        held_before = inv.hold_list_count()
        inv.hold_current_inventory()
        assert inv.total_items() == 0 and inv.hold_list_count() == held_before + 1
        dlg = inv.open_hold_list()
        assert dlg.is_open()
        dlg.resume(0)
        inv.page.wait_for_timeout(500)
        assert inv.current_mode() == mode, f"resumed a {mode} hold into {inv.current_mode()} mode"
        assert inv.total_items() == before_n and inv.cart_total_price() == before_total
        assert inv.cart_rows() == before_rows, "resumed cart rows differ from the held ones"
        assert inv.hold_list_count() == held_before, "resumed hold is still in the Hold List"

    @pytest.mark.parametrize("held,other", [("Default", "Opening Stock"), ("TP/VAT", "Default"),
                                            ("Opening Stock", "TP/VAT")],
                             ids=["default_vs_opening", "tpvat_vs_default", "opening_vs_tpvat"])
    @allure.story("The Hold List is per mode: a hold made in one mode is not listed (or resumable) in another mode")
    def test_hold_list_is_per_mode(self, modes, held, other):
        inv = modes.go(other)
        other_before = inv.hold_list_count()
        modes.fill(held, "two_plain")
        rows, n = inv.cart_rows(), inv.total_items()
        held_before = inv.hold_list_count()
        inv.hold_current_inventory()
        assert inv.hold_list_count() == held_before + 1
        modes.go(other)
        try:
            assert inv.hold_list_count() == other_before,                 f"a {held} hold changed the {other} Hold List count ({other_before} -> {inv.hold_list_count()})"
        finally:
            modes.go(held)
            inv.open_hold_list().resume(0)           # always put the hold back so nothing is left behind
        inv.page.wait_for_timeout(500)
        assert inv.current_mode() == held and inv.total_items() == n and inv.cart_rows() == rows


@allure.epic("Inventory")
@allure.feature("Cross-mode - held inventory completed (spec 34)")
class TestHeldInventoryCompletion:

    @allure.story("Completing a resumed hold leaves it out of the Hold List and creates the inventory record")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_complete_held_inventory(self, modes):
        flow = modes.flows["Default"]
        j = modes.fill("Default", "single_plain")
        inv = modes.inv
        before = inv.hold_list_count()
        inv.hold_current_inventory()
        assert inv.hold_list_count() == before + 1
        inv.open_hold_list().resume(0)
        inv.page.wait_for_timeout(500)
        assert inv.hold_list_count() == before
        co = flow.open_checkout(j)
        flow.pay(co, j, flow.oracle(j).final_price)
        dlg = flow.complete_and_open_details(co, j)
        assert dlg.item_row_by_batch(j.batches[0]) is not None, "completed inventory does not contain the held line"
        inv = flow.inventory.open("Default")
        assert inv.hold_list_count() == before, "Hold List still lists the completed inventory"
