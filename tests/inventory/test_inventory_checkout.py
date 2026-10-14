"""Inventory Checkout - discount, Free-Qty exclusion, and completion
(spec sections 35-42).

BUG-INV-001/002/003 tests assert the SPEC-DESIRED behaviour and are expected
to stay red until those defects are fixed (same convention as
tests/products/test_add_product.py::TestWholesalePriceOptional).
"""
from __future__ import annotations

import re

import allure
import pytest

from pages.inventory_record_page import InventoryRecordPage

pytestmark = [pytest.mark.inventory]


def _money(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", text)
    assert m, f"could not parse a money value out of {text!r}"
    return float(m.group().replace(",", ""))


def _eligible_and_free_qty_products(inventory_data: dict) -> tuple[str, str]:
    """(eligible product with no free qty, product that will carry free qty)."""
    products = inventory_data.get("existing", {}).get("products_sample", ["100%", "TEST PRODUCT"])
    return products[0], (products[1] if len(products) > 1 else products[0])


def _build_discount_test_cart(inventory, inventory_data) -> tuple[str, str]:
    """Cart = one eligible line (no Free Qty) + one line WITH Free Qty, mirroring
    the exploratory repro for BUG-INV-001/003 (21.60 free-qty line + 210.00
    eligible line = 231.60 total)."""
    eligible, free_qty_product = _eligible_and_free_qty_products(inventory_data)
    inventory.add_item_to_cart(product=free_qty_product, box_qty=3, free_qty=5,
                               batch_no="QA_AUTO_INV_CO_FREE")
    inventory.add_item_to_cart(product=eligible, box_qty=2,
                               batch_no="QA_AUTO_INV_CO_ELIGIBLE")
    return eligible, free_qty_product


@allure.epic("Inventory")
@allure.feature("Inventory Checkout")
class TestCheckoutBasics:

    @allure.story("Checkout shows the cart items and a Total Price matching the cart (spec section 36)")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_checkout_totals_match_cart(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=1, batch_no="QA_AUTO_INV_CO_SMOKE")
        cart_total = _money(inventory.cart_total_price_text())
        checkout = inventory.go_to_checkout()
        checkout_total = _money(checkout.total_price())
        assert checkout_total == pytest.approx(cart_total, abs=0.01), (
            f"Checkout Total Price {checkout_total} != cart Total Price {cart_total}"
        )

    @allure.story("Discount type Flat (Tk) reduces Final Price by exactly the flat amount")
    @pytest.mark.regression
    def test_flat_discount_reduces_final_price(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=1, batch_no="QA_AUTO_INV_CO_FLAT")
        checkout = inventory.go_to_checkout()
        total_before = _money(checkout.total_price())
        checkout.set_discount(5, "Tk")
        final = _money(checkout.final_price())
        assert final == pytest.approx(total_before - 5, abs=0.01), (
            f"Final Price {final} != Total Price({total_before}) - flat discount(5)"
        )


@allure.epic("Inventory")
@allure.feature("Discount + Free Qty exclusion (BUG-INV-001 / BUG-INV-003)")
class TestDiscountExcludesFreeQty:

    @allure.story("BUG-INV-001: a percentage discount must exclude Free-Qty lines from its base (spec 38-39)")
    @allure.issue("BUG-INV-001")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    @pytest.mark.regression
    def test_discount_amount_excludes_free_qty_line(self, inventory, inventory_data):
        _build_discount_test_cart(inventory, inventory_data)
        checkout = inventory.go_to_checkout()
        cart_total = _money(checkout.total_price())

        checkout.set_discount(10, "%")
        discount_amount = _money(checkout.discount_amount())
        allure.attach(f"cart total={cart_total}, 10% discount amount shown={discount_amount}",
                      name="observed")

        # Eligible-only base = cart total minus the free-qty line's Total Price
        # (21.60 in the standard repro). We don't hardcode 21.60 here in case
        # product defaults drift - instead assert the discount is NOT simply
        # 10% of the full cart total, which is the confirmed defect.
        full_total_discount = round(cart_total * 0.10, 2)
        assert discount_amount != pytest.approx(full_total_discount, abs=0.01), (
            f"BUG-INV-001 reproduced: Discount Amount {discount_amount} equals 10% of the FULL "
            f"cart total ({full_total_discount}) - the Free-Qty line was not excluded from the "
            "discount base per spec sections 38-39"
        )

    @allure.story("BUG-INV-003: the amount paid at checkout must match the Final Price actually recorded")
    @allure.issue("BUG-INV-003")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_checkout_preview_matches_saved_record(self, inventory, inventory_data):
        _build_discount_test_cart(inventory, inventory_data)
        checkout = inventory.go_to_checkout()
        checkout.set_discount(10, "%")
        final_price_preview = _money(checkout.final_price())
        due_preview = _money(checkout.due())
        assert due_preview == pytest.approx(0, abs=0.01), (
            f"checkout page itself already shows a non-zero Due ({due_preview}) before submission"
        )

        supplier = checkout.select_first_supplier()
        assert checkout.complete_enabled(), "Complete Inventory stayed disabled after selecting a supplier"
        checkout.complete()

        record = InventoryRecordPage(inventory.page).open()
        dlg = record.open_details(0)
        recorded_final_price = _money(dlg.final_price())
        recorded_paid = _money(dlg.total_paid())
        status = dlg.payment_status()
        allure.attach(
            f"checkout preview: final={final_price_preview}, due={due_preview} | "
            f"saved record: final={recorded_final_price}, paid={recorded_paid}, status={status}",
            name="checkout vs record",
        )
        assert status.strip().lower() == "paid" and recorded_paid == pytest.approx(recorded_final_price, abs=0.01), (
            f"BUG-INV-003 reproduced: checkout showed Due=0 (paid={final_price_preview}), but the "
            f"saved inventory record has Final Price={recorded_final_price}, Total Paid={recorded_paid}, "
            f"Payment Status={status!r} - the two do not reconcile"
        )
        dlg.close()


@allure.epic("Inventory")
@allure.feature("Complete Inventory - success feedback (BUG-INV-002)")
class TestCompleteInventorySuccessModal:

    @allure.story("BUG-INV-002: a success modal with the transaction summary should appear after checkout (spec 42.1)")
    @allure.issue("BUG-INV-002")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_success_modal_appears_after_checkout(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=1, batch_no="QA_AUTO_INV_CO_MODAL")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        checkout.complete()

        modal = inventory.page.get_by_text("Inventory Complete", exact=True)
        try:
            modal.wait_for(state="visible", timeout=5_000)
        except Exception:
            pass
        assert modal.count() > 0, (
            "BUG-INV-002 reproduced: no 'Inventory Complete' success modal appeared after checkout "
            "(spec section 42.1 requires Inventory ID / Supplier / Payment Status / Totals and "
            "Invoice / Hold List / New Inventory actions); only a toast + redirect to /inventory was observed"
        )


@allure.epic("Inventory")
@allure.feature("Complete Inventory - double-submit protection (BUG-INV-012)")
class TestCompleteInventoryDoubleClick:

    @allure.story("BUG-INV-012: double-clicking Complete Inventory must not create duplicate transactions")
    @allure.issue("BUG-INV-012")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_double_click_does_not_duplicate_transaction(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)

        # Baseline row count BEFORE this test's transaction exists.
        before_count = InventoryRecordPage(inventory.page).open().row_count()

        inventory.open("Default")
        inventory.add_item_to_cart(product=eligible, box_qty=1, batch_no="QA_AUTO_INV_CO_DBLCLICK")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        assert checkout.complete_enabled(), "Complete Inventory stayed disabled after selecting a supplier"

        statuses = checkout.complete_double_click()
        allure.attach(str(statuses), name="POST inventories/create responses")
        successes = [s for s in statuses if s in (200, 201)]

        record = InventoryRecordPage(inventory.page).open()
        after_count = record.row_count()
        created = after_count - before_count

        assert len(successes) <= 1 and created <= 1, (
            f"BUG-INV-012 reproduced: a rapid double-click on Complete Inventory produced "
            f"{len(successes)} successful create responses ({statuses}) and {created} new "
            f"Inventory Record row(s) (expected at most 1 of each) - the same purchase was "
            f"committed twice, doubling both stock received and payment recorded."
        )


@allure.epic("Inventory")
@allure.feature("Paid/Due/Advance summary labelling (BUG-INV-016)")
class TestCheckoutAdvanceLabel:

    @allure.story("BUG-INV-016: the live Checkout summary must relabel 'Due' to 'Advance' once Paid Amount exceeds Final Price")
    @allure.issue("BUG-INV-016")
    @allure.severity(allure.severity_level.MINOR)
    @pytest.mark.negative
    @pytest.mark.regression
    def test_summary_relabels_advance_when_overpaid(self, inventory, inventory_data):
        eligible, _ = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=1, price_per_box=100,
                                   batch_no="QA_AUTO_INV_CO_ADVANCE_LABEL")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        final = _money(checkout.final_price())
        checkout.set_paid_amount(final + 50)

        due_text = checkout.due()
        advance_shown = checkout.advance_label_shown()
        allure.attach(f"final={final}, due_field_text={due_text!r}, advance_label_shown={advance_shown}",
                      name="observed")
        assert advance_shown, (
            f"BUG-INV-016 reproduced: after overpaying by 50 (final={final}), the checkout summary "
            f"panel still shows a 'Due' row (Due field text={due_text!r}) instead of relabelling to "
            "'Advance' with a positive amount - the post-completion Inventory Record correctly shows "
            "'Advance', so this is a pre-submission display gap, not a calculation error."
        )


@allure.epic("Inventory")
@allure.feature("Checkout - Flat discount type (BUG-INV-020)")
class TestFlatDiscountCompletion:

    @allure.story("BUG-INV-020: a Flat (Tk) discount must complete successfully, exactly like a Percentage discount")
    @allure.issue("BUG-INV-020")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.negative
    @pytest.mark.regression
    @pytest.mark.integration
    def test_flat_discount_completes_successfully(self, inventory, inventory_data):
        eligible, other = _eligible_and_free_qty_products(inventory_data)
        inventory.add_item_to_cart(product=eligible, box_qty=1, price_per_box=100,
                                   batch_no="QA_AUTO_INV_CO_FLAT_DISC_1")
        inventory.add_item_to_cart(product=other, box_qty=1, price_per_box=110,
                                   batch_no="QA_AUTO_INV_CO_FLAT_DISC_2")
        checkout = inventory.go_to_checkout()
        checkout.select_first_supplier()
        checkout.set_discount(15, "Tk")
        final_shown = _money(checkout.final_price())

        status, body = checkout.complete_capturing_response()
        allure.attach(f"final price shown={final_shown}, create response status={status}, body={body}",
                      name="observed")
        assert status is not None and status < 300, (
            f"BUG-INV-020 reproduced: Complete Inventory with a Flat discount active (checkout showed "
            f"Final Price {final_shown} correctly) returned HTTP {status} ({body}) instead of "
            "succeeding - the backend rejects the discountType value the frontend sends for Flat "
            "discounts (\"FLAT\" is not a recognised InventoryDiscountType), and the checkout page "
            "shows zero visible error to the user, who is left thinking nothing happened."
        )
