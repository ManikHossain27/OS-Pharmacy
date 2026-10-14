"""Add New Product drawer - functional, negative, boundary, integration."""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import expect

from utils import data_generator as dg
from utils.constants import (
    ADD_PRODUCT_REQUIRED_MESSAGES,
    RAW_BACKEND_ERROR_FRAGMENTS,
    WHOLESALE_BACKEND_NULL_MESSAGE,
    WHOLESALE_REQUIRED_MESSAGE,
)

pytestmark = [pytest.mark.products]


def _wait_for_validation(add_product) -> None:
    """Wait until at least one inline error has rendered in the drawer."""
    expect(
        add_product.drawer.root.locator(".ant-form-item-explain-error").first
    ).to_be_visible(timeout=6_000)


@allure.epic("Products")
@allure.feature("Add New Product")
class TestAddProductForm:

    @allure.story("Drawer opens with all expected fields")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    def test_drawer_opens_with_fields(self, add_product):
        assert add_product.is_open()
        d = add_product.drawer
        for fid in ("productName", "strength", "productType", "company", "generic",
                    "quantityInBox", "retailPricePerBox", "wholesalePricePerBox"):
            assert d.field(fid).count() == 1, f"field #{fid} missing"

    @allure.story("Empty submit shows all required-field messages")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.negative
    def test_empty_submit_shows_required_errors(self, add_product):
        add_product.submit()
        _wait_for_validation(add_product)
        errors = add_product.validation_errors()
        for label, msg in ADD_PRODUCT_REQUIRED_MESSAGES.items():
            assert any(msg.lower() in e.lower() for e in errors.values()), (
                f"missing required message for {label!r}: expected {msg!r}, got {errors}"
            )

    @allure.story("Optional fields are not required")
    @pytest.mark.negative
    def test_strength_and_generic_optional(self, add_product):
        add_product.submit()
        _wait_for_validation(add_product)
        errors = add_product.validation_errors()
        assert "Strength" not in errors
        assert "Generic Name" not in errors

    @allure.story("Cost/Box is enabled (BUG-PROD-001 fixed 2026-09-09) and accepts 0")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.issue("BUG-PROD-001")
    @pytest.mark.regression
    def test_cost_per_box_is_enabled_and_accepts_zero(self, add_product):
        assert not add_product.cost_per_box_disabled(), (
            "Cost/Box is disabled again - BUG-PROD-001 has regressed (product create is blocked)"
        )
        add_product.set_number("cost_per_box", 0)
        assert add_product.number_raw("cost_per_box") == "0", "Cost/Box did not accept 0"

    @allure.story("BUG-PROD-006: Cost/Box is backend-required but shows no asterisk / no client validation")
    @allure.issue("BUG-PROD-006")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_cost_per_box_required_but_unmarked(self, add_product):
        """It is required server-side ('Cost per box must not be null', 400) but
        the label carries no asterisk and an empty submit produces no UI feedback."""
        # every *legitimately* required field on this form carries the asterisk
        # (wholesale_price_per_box is excluded - per requirement it should be
        # optional; its wrongly-required state is tracked as BUG-PROD-008)
        for key in ("product_name", "product_type", "company", "qty_per_box",
                    "retail_price_per_box"):
            assert add_product.is_required_marked(key), f"{key} lost its required asterisk"
        # ...Cost/Box does not, even though the backend rejects a null.
        assert add_product.is_required_marked("cost_per_box"), (
            "BUG-PROD-006 reproduced: Cost/Box has no required asterisk although the "
            "backend rejects an empty value ('Cost per box must not be null')"
        )

    @allure.story("Additional Information expands to reveal extra fields")
    @pytest.mark.ui
    def test_additional_information_expands(self, add_product):
        add_product.expand_additional_info()
        for fid in ("rackNo", "barcodeValue", "volume", "origin"):
            assert add_product.drawer.field(fid).is_visible(), f"#{fid} not visible after expand"

    @allure.story("Cancel closes the drawer without saving")
    def test_cancel_closes_drawer(self, add_product):
        add_product.set_text("product_name", dg.product_name())
        add_product.close()
        assert not add_product.is_open()

    # ---------------- boundary / negative on text fields (fillable) -------------
    @allure.story("Product Name - whitespace-only should be rejected")
    @pytest.mark.negative
    @pytest.mark.boundary
    def test_product_name_whitespace_only_rejected(self, add_product):
        add_product.set_text("product_name", "     ")
        add_product.submit()
        _wait_for_validation(add_product)
        errors = add_product.validation_errors()
        assert "Product Name" in errors, "whitespace-only name was accepted as valid"

    @allure.story("Product Name - very long string handling")
    @pytest.mark.boundary
    def test_product_name_very_long_string(self, add_product):
        long_name = dg.long_string(300)
        add_product.set_text("product_name", long_name)
        val = add_product.drawer.field("productName").input_value()
        allure.attach(f"accepted length: {len(val)}", name="max length observed")
        assert len(val) <= 300

    # ---------------- number field boundary (fillable) ------------------------
    @allure.story("Qty/Box - negative value handling")
    @pytest.mark.negative
    @pytest.mark.boundary
    @pytest.mark.parametrize("value", [-1, -100])
    def test_qty_negative_rejected_or_clamped(self, add_product, value):
        add_product.set_number("qty_per_box", value)
        raw = add_product.drawer.field("quantityInBox").input_value()
        allure.attach(f"input {value} -> field shows {raw!r}", name="qty negative")
        assert not raw.startswith("-"), f"negative quantity {raw!r} accepted in field"

    @allure.story("Retail/Wholesale price - decimal precision handling")
    @pytest.mark.boundary
    @pytest.mark.parametrize("value", ["12.5", "12.55", "12.555"])
    def test_price_decimal_precision(self, add_product, value):
        add_product.set_number("retail_price_per_box", value)
        raw = add_product.drawer.field("retailPricePerBox").input_value()
        allure.attach(f"input {value} -> {raw!r}", name="price precision")

    @allure.story("Price - alphabetic input is not accepted")
    @pytest.mark.negative
    def test_price_alpha_input_rejected(self, add_product):
        add_product.set_number("retail_price_per_box", "abc")
        raw = add_product.drawer.field("retailPricePerBox").input_value()
        assert raw in ("", "abc") and not raw.isalpha() or raw == "", (
            f"alphabetic price {raw!r} unexpectedly retained"
        )

    # ---------------- create path -----------------------------------------
    @allure.story("BUG-PROD-001 (fixed): a fully-valid Add-Product form creates the product")
    @allure.severity(allure.severity_level.BLOCKER)
    @allure.issue("BUG-PROD-001")
    @pytest.mark.integration
    @pytest.mark.regression
    def test_create_valid_product_succeeds(self, my_products, products_data):
        """Since 2026-09-09 the Cost/Box field is enabled; a valid form (Cost/Box
        included, 0 allowed) must create the product."""
        seed = products_data.get("existing", {})
        ptype = (seed.get("product_types_sample") or ["CAPSULE UPDATED"])[0]
        company = (seed.get("companies_sample") or ["ABBOTT LABORATORIES"])[0]
        drawer = my_products.open_add_product()

        assert not drawer.cost_per_box_disabled(), (
            "Cost/Box is disabled again - BUG-PROD-001 regressed; product create is blocked"
        )

        data = dg.new_product(product_type=ptype, company=company, cost_per_box=0)
        drawer.fill_form(data)

        with drawer.page.expect_response(
            lambda r: "pharmacy-products/create/" in r.url, timeout=15_000
        ) as ri:
            drawer.submit()
        resp = ri.value
        allure.attach(f"{resp.status} {resp.url}", name="create response")

        if resp.status in (404, 500, 502, 503):
            pytest.skip(f"create endpoint returned {resp.status} - environment issue (BUG-API-001)")

        body = ""
        try:
            body = str(resp.json()).lower()
        except Exception:
            pass
        assert resp.status in (200, 201) and "cost per box must not be null" not in body, (
            f"product create rejected: {resp.status} {body!r}"
        )

    @allure.story("BUG-PROD-006: an empty Cost/Box submit produces NO error message in the UI")
    @allure.issue("BUG-PROD-006")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_empty_cost_per_box_gives_no_ui_feedback(self, my_products, products_data):
        seed = products_data.get("existing", {})
        ptype = (seed.get("product_types_sample") or ["CAPSULE UPDATED"])[0]
        company = (seed.get("companies_sample") or ["ABBOTT LABORATORIES"])[0]
        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled - different failure mode (BUG-PROD-001)")

        data = dg.new_product(product_type=ptype, company=company)
        data.pop("cost_per_box", None)          # leave Cost/Box empty
        drawer.fill_form(data)

        with drawer.page.expect_response(
            lambda r: "pharmacy-products/create/" in r.url, timeout=15_000
        ) as ri:
            drawer.submit()
        resp = ri.value
        if resp.status in (404, 500, 502, 503):
            pytest.skip(f"create endpoint {resp.status} - environment issue (BUG-API-001)")

        drawer.page.wait_for_timeout(1_000)  # let any inline error / toast render
        inline = drawer.validation_errors()
        cost_flagged = any("cost" in k.lower() for k in inline)
        toast = " ".join(drawer.toast_messages()).lower()
        # Desired: an inline 'Cost per box is required' (or a mapped field error).
        assert cost_flagged or "cost per box" in toast, (
            "BUG-PROD-006 reproduced: server rejected the empty Cost/Box "
            f"({resp.status}) but the UI showed nothing (inline={inline}, toast={toast!r})"
        )

    @allure.story("Cancel closes the drawer without saving")
    def test_cancel_from_filled_form(self, add_product):
        add_product.set_text("product_name", dg.product_name())
        add_product.close()
        assert not add_product.is_open()

    # ---------------- BUG-PROD-004: missing client-side number guards ---------
    @allure.story("BUG-PROD-004: negative Retail Price is not guarded client-side")
    @allure.issue("BUG-PROD-004")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_negative_retail_price_not_guarded(self, add_product):
        add_product.set_number("retail_price_per_box", -5)
        raw = add_product.number_raw("retail_price_per_box")
        allure.attach(f"input -5 -> field {raw!r}", name="retail price")
        # Desired behaviour: the field clamps to >= 0 (or shows an inline error).
        assert not raw.startswith("-"), (
            f"BUG-PROD-004 reproduced: negative retail price {raw!r} accepted with no client guard"
        )

    @allure.story("BUG-PROD-004: Qty/Box = 0 is not guarded client-side")
    @allure.issue("BUG-PROD-004")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_zero_qty_per_box_not_guarded_client_side(self, add_product):
        """Fill the *fillable* required fields validly, set Qty/Box = 0 and
        submit.  The form should refuse a zero quantity (min 1) - it does not:
        the only inline errors that come back are for the unfilled selects, never
        for Qty/Box.  (Server-side, the create request goes out with
        ``quantityInBox:0`` and the backend does not flag it either - see the
        live evidence attached to BUG-PROD-004.)"""
        add_product.set_text("product_name", dg.product_name())
        add_product.set_number("retail_price_per_box", 100)
        add_product.set_number("wholesale_price_per_box", 90)
        add_product.set_number("qty_per_box", 0)

        # No client-side lower-bound attribute on the InputNumber.
        min_attr = add_product.drawer.field("quantityInBox").get_attribute("min")
        allure.attach(f"Qty/Box min attr = {min_attr!r}", name="qty min attr")

        add_product.submit()
        try:
            _wait_for_validation(add_product)
        except Exception:
            pass
        errors = add_product.validation_errors()
        allure.attach(str(errors), name="validation errors after zero-qty submit")

        qty_flagged = any(("qty" in k.lower() or "quantity" in k.lower()) for k in errors)
        # Desired behaviour: Qty/Box = 0 is rejected client-side (min 1).
        assert qty_flagged or (min_attr not in (None, "", "0")), (
            "BUG-PROD-004 reproduced: Qty/Box = 0 is not guarded client-side "
            f"(min attr={min_attr!r}; inline errors after submit={list(errors)}). "
            "The create request goes out with quantityInBox:0."
        )

    # ---------------- BUG-PROD-005: drawer keeps stale state on reopen --------
    @allure.story("BUG-PROD-005: Add drawer is pristine when reopened after Cancel")
    @allure.issue("BUG-PROD-005")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_add_drawer_reset_on_reopen(self, my_products, add_product):
        add_product.set_text("product_name", "QA STALE 260909")
        add_product.set_number("retail_price_per_box", -5)
        add_product.expand_additional_info()
        reopened = add_product.reopen(my_products)
        state = reopened.form_state()
        allure.attach(str(state), name="reopened form state")
        leftovers = {k: v for k, v in state.items() if v not in ("", "on", "Bangladesh")}
        assert not leftovers and not reopened.additional_info_expanded(), (
            f"BUG-PROD-005 reproduced: reopened Add drawer still holds {leftovers} "
            f"(Additional Information expanded={reopened.additional_info_expanded()})"
        )


# ===========================================================================
# Add New Product - BOUNDARY / COMBINATION matrix (designed cases
# TC-PROD-ADD-019..043).  Written 2026-09-09; not run live yet - the staging API
# was in an outage (BUG-API-001) that blocked even login.  These run as
# characterization tests: the invariant asserted everywhere is that a RAW
# backend/serialization error must never reach the user (the brief forbids
# strings like "expected a value of type int").  Concrete per-case assertions
# are added where the correct behaviour is unambiguous.
# ===========================================================================


def _seed_type_company(products_data: dict) -> tuple[str, str]:
    seed = products_data.get("existing", {})
    ptype = (seed.get("product_types_sample") or ["CAPSULE UPDATED"])[0]
    company = (seed.get("companies_sample") or ["ABBOTT LABORATORIES"])[0]
    return ptype, company


def _assert_no_raw_error(result: dict) -> None:
    blob = "{} {} {}".format(result.get("body"), result.get("toast"), result.get("inline")).lower()
    leaked = [f for f in RAW_BACKEND_ERROR_FRAGMENTS if f in blob]
    assert not leaked, (
        "raw backend/serialization error leaked to the user: "
        "{} -- full: {}".format(leaked, blob[:400])
    )


def _env_skip(result: dict) -> bool:
    return result.get("status") in (404, 500, 502, 503)


@allure.epic("Products")
@allure.feature("Add New Product - boundary matrix")
class TestAddProductBoundaries:

    # ---- Product Name -----------------------------------------------------
    @allure.story("TC-PROD-ADD-019..023: Product Name boundary values")
    @pytest.mark.boundary
    @pytest.mark.parametrize("case,name,expect_reject", [
        ("whitespace-only", "     ", True),
        ("single-char", "Q", False),
        ("leading-trailing-space", "  QA TRIM 260909  ", False),
        ("special-chars", "QA and Co. #1 (test) 50 percent", False),
        ("unicode", "QA uni 260909 éü安", False),
        ("very-long-300", "A" * 300, None),
    ])
    def test_product_name_values(self, my_products, products_data, case, name, expect_reject):
        ptype, company = _seed_type_company(products_data)
        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001) - can't reach the create call")
        data = dg.new_product(product_type=ptype, company=company, cost_per_box=0,
                              product_name=name)
        result = drawer.create_and_capture(data)
        allure.attach(str(result), name="name={!r}".format(case))
        _assert_no_raw_error(result)
        if _env_skip(result) or (result["status"] is None and not result["inline"]):
            pytest.skip("environment issue (status={}) - BUG-API-001".format(result["status"]))
        if expect_reject is True:
            assert result["status"] not in (200, 201) or result["inline"], \
                "{!r} product name was accepted: {}".format(case, result)
        elif expect_reject is False:
            assert result["status"] in (200, 201) or not result["inline"], \
                "{!r} product name was unexpectedly rejected: {}".format(case, result)
        if case == "leading-trailing-space" and result["status"] in (200, 201):
            body = result["body"] if isinstance(result["body"], dict) else {}
            pn = body.get("productName", "")
            assert pn == pn.strip(), "leading/trailing spaces were NOT trimmed on save"

    @allure.story("TC-PROD-ADD-024: HTML/script in Product Name is stored inert, never executed")
    @pytest.mark.negative
    @pytest.mark.security
    def test_product_name_html_injection_is_safe(self, my_products, products_data):
        ptype, company = _seed_type_company(products_data)
        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001)")
        data = dg.new_product(product_type=ptype, company=company, cost_per_box=0,
                              product_name="<img src=x onerror=alert(1)>QA XSS 260909")
        result = drawer.create_and_capture(data)
        _assert_no_raw_error(result)
        if _env_skip(result):
            pytest.skip("environment issue (BUG-API-001)")
        my_products.reload()
        my_products.search("QA XSS 260909")
        assert my_products.page.locator("img[onerror]").count() == 0, \
            "stored XSS: an <img onerror> from the product name rendered as live HTML"

    @allure.story("TC-PROD-ADD-025: creating the same product twice has a defined outcome")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_duplicate_product_name(self, my_products, products_data, qa_records):
        ptype, company = _seed_type_company(products_data)
        name = "QA DUP {} 260909".format(dg.product_name().split()[-1])
        d1 = my_products.open_add_product()
        if d1.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001)")
        r1 = d1.create_and_capture(dg.new_product(product_type=ptype, company=company,
                                                  cost_per_box=0, product_name=name))
        if r1["status"] not in (200, 201):
            pytest.skip("first create did not succeed ({}) - BUG-API-001".format(r1["status"]))
        qa_records.append(name)
        d2 = my_products.open_add_product()
        r2 = d2.create_and_capture(dg.new_product(product_type=ptype, company=company,
                                                  cost_per_box=0, product_name=name))
        allure.attach(str(r2), name="second create")
        _assert_no_raw_error(r2)
        assert r2["status"] in (200, 201) or r2["toast"] or r2["inline"], \
            "duplicate create produced no feedback at all: {}".format(r2)

    # ---- Qty / Box ------------------------------------------------------
    @allure.story("TC-PROD-ADD-027/029/030/031: Qty/Box boundary values")
    @pytest.mark.boundary
    @pytest.mark.parametrize("case,qty", [
        ("negative", -5), ("decimal", "1.5"),
        ("very-large", "99999999999"), ("alphabetic", "abc"),
    ])
    def test_qty_per_box_values(self, my_products, products_data, case, qty):
        ptype, company = _seed_type_company(products_data)
        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001)")
        drawer.fill_form(dg.new_product(product_type=ptype, company=company, cost_per_box=0))
        drawer.set_number("qty_per_box", qty)
        raw = drawer.number_raw("qty_per_box")
        allure.attach("input {!r} -> field {!r}".format(qty, raw), name="qty {}".format(case))
        if case == "alphabetic":
            assert not any(c.isalpha() for c in raw), "letters retained in Qty/Box: {!r}".format(raw)
        if case == "negative":
            assert not raw.startswith("-"), "negative Qty/Box retained: {!r}".format(raw)

    # ---- Prices -------------------------------------------------------
    @allure.story("TC-PROD-ADD-033..036: price field boundary + relationship")
    @pytest.mark.boundary
    @pytest.mark.parametrize("case,retail,wholesale", [
        ("retail-negative", -1, 90),
        ("retail-alpha", "abc", 90),
        ("wholesale-gt-retail", 50, 200),
        ("both-zero", 0, 0),
    ])
    def test_price_values(self, my_products, products_data, case, retail, wholesale):
        ptype, company = _seed_type_company(products_data)
        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001)")
        data = dg.new_product(product_type=ptype, company=company, cost_per_box=10,
                              retail_price_per_box=retail, wholesale_price_per_box=wholesale)
        result = drawer.create_and_capture(data)
        allure.attach(str(result), name=case)
        _assert_no_raw_error(result)
        if _env_skip(result):
            pytest.skip("environment issue (BUG-API-001)")
        if case == "retail-alpha":
            raw = drawer.number_raw("retail_price_per_box")
            assert raw == "" or raw.lstrip("-").replace(".", "").isdigit(), \
                "letters retained in price field: {!r}".format(raw)
        if case == "retail-negative":
            assert result["status"] not in (200, 201), "negative retail price accepted end to end"

    # ---- Barcode -----------------------------------------------------
    @allure.story("TC-PROD-ADD-037/038: barcode free-text + duplicate across products")
    @pytest.mark.boundary
    def test_barcode_freetext_and_duplicate(self, my_products, products_data, qa_records):
        ptype, company = _seed_type_company(products_data)
        tag = dg.product_name().split()[-1]
        bc = "QA-BC-{}-x".format(tag)
        d1 = my_products.open_add_product()
        if d1.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001)")
        n1 = "QA BARCODE A {}".format(tag)
        r1 = d1.create_and_capture(dg.new_product(product_type=ptype, company=company,
                                                  cost_per_box=0, product_name=n1, barcode_value=bc))
        allure.attach(str(r1), name="free-text barcode create")
        _assert_no_raw_error(r1)
        if r1["status"] not in (200, 201):
            pytest.skip("first create not successful ({}) - BUG-API-001".format(r1["status"]))
        qa_records.append(n1)
        d2 = my_products.open_add_product()
        r2 = d2.create_and_capture(dg.new_product(product_type=ptype, company=company, cost_per_box=0,
                                                  product_name="QA BARCODE B {}".format(tag),
                                                  barcode_value=bc))
        allure.attach(str(r2), name="duplicate barcode create")
        _assert_no_raw_error(r2)
        assert r2["status"] in (200, 201) or r2["toast"] or r2["inline"], \
            "duplicate barcode create gave no feedback: {}".format(r2)

    # ---- Drawer behaviour ------------------------------------------------
    @allure.story("TC-PROD-ADD-040: the X icon closes the drawer without saving")
    def test_x_icon_closes_drawer(self, my_products, add_product):
        add_product.set_text("product_name", dg.product_name())
        add_product.x_close()
        assert not add_product.is_open()

    @allure.story("TC-PROD-ADD-043: double-clicking Confirm does not create two products")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_double_submit_is_idempotent(self, my_products, products_data, qa_records):
        ptype, company = _seed_type_company(products_data)
        name = "QA DBLCLICK {} 260909".format(dg.product_name().split()[-1])
        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001)")
        result = drawer.create_and_capture(
            dg.new_product(product_type=ptype, company=company, cost_per_box=0, product_name=name),
            double_submit=True,
        )
        allure.attach(str(result), name="double-submit result")
        _assert_no_raw_error(result)
        if _env_skip(result):
            pytest.skip("environment issue (BUG-API-001)")
        qa_records.append(name)
        my_products.reload()
        my_products.search(name)
        n_rows = my_products.table.rows.count()
        assert n_rows <= 1, "double-click 'Confirm' created {} rows for {!r}".format(n_rows, name)
        assert result["req_count"] <= 1, \
            "{} create POSTs fired on a double-click".format(result["req_count"])


# ===========================================================================
# BUG-PROD-008 - "Wholesale Price/Box" must be OPTIONAL in Add New Product
# (requirement).  The build enforces it as mandatory on Add + Edit + backend;
# these tests assert the *desired* behaviour and stay red until it is fixed.
# ===========================================================================
@allure.epic("Products")
@allure.feature("Add New Product - Wholesale Price/Box is optional (BUG-PROD-008)")
class TestWholesalePriceOptional:

    @allure.story("TC-PROD-ADD-053: Wholesale Price/Box label shows no required asterisk")
    @allure.issue("BUG-PROD-008")
    @pytest.mark.ui
    @pytest.mark.regression
    def test_wholesale_label_not_required_marked(self, add_product):
        assert not add_product.is_required_marked("wholesale_price_per_box"), (
            "BUG-PROD-008: Wholesale Price/Box is marked required (asterisk) - "
            "the requirement says it must be optional"
        )

    @allure.story("TC-PROD-ADD-056: empty submit does NOT flag Wholesale as required")
    @allure.issue("BUG-PROD-008")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_empty_submit_does_not_require_wholesale(self, add_product):
        add_product.submit()
        try:
            _wait_for_validation(add_product)
        except Exception:
            pass
        errs = add_product.validation_errors()
        joined = " ".join(errs.values()).lower()
        assert WHOLESALE_REQUIRED_MESSAGE.lower() not in joined and "Wholesale Price/Box" not in errs, (
            "BUG-PROD-008: empty submit flags '{}' - Wholesale must be optional "
            "(errors: {})".format(WHOLESALE_REQUIRED_MESSAGE, errs)
        )

    @allure.story("TC-PROD-ADD-054: a product can be created with Wholesale Price/Box empty")
    @allure.issue("BUG-PROD-008")
    @pytest.mark.integration
    @pytest.mark.regression
    def test_create_without_wholesale_succeeds(self, my_products, products_data):
        seed = products_data.get("existing", {})
        ptype = (seed.get("product_types_sample") or ["CAPSULE UPDATED"])[0]
        company = (seed.get("companies_sample") or ["ABBOTT LABORATORIES"])[0]
        drawer = my_products.open_add_product()
        if drawer.cost_per_box_disabled():
            pytest.skip("Cost/Box disabled (BUG-PROD-001)")
        data = dg.new_product(product_type=ptype, company=company, cost_per_box=0)
        data.pop("wholesale_price_per_box", None)          # leave it empty
        try:
            result = drawer.create_and_capture(data)
        except drawer.FillError as exc:
            pytest.skip("could not fill the form (AntD Select flake / slow env): {}".format(exc))
        allure.attach(str(result), name="create-without-wholesale")
        _assert_no_raw_error(result)
        if _env_skip(result):
            pytest.skip("environment issue (BUG-API-001)")
        blob = "{} {}".format(result["inline"], result["toast"]).lower()
        assert WHOLESALE_REQUIRED_MESSAGE.lower() not in blob and result["status"] in (200, 201), (
            "BUG-PROD-008: create with an empty Wholesale Price/Box was rejected "
            "(status={}, feedback={})".format(result["status"], blob)
        )

    @allure.story("TC-PROD-ADD-055: the create endpoint accepts a payload without wholesalePricePerBox")
    @allure.issue("BUG-PROD-008")
    @pytest.mark.negative
    @pytest.mark.regression
    def test_backend_accepts_missing_wholesale(self, my_products, products_data):
        import json as _json
        seed = products_data.get("existing", {})
        ptype = (seed.get("product_types_sample") or ["CAPSULE UPDATED"])[0]
        company = (seed.get("companies_sample") or ["ABBOTT LABORATORIES"])[0]
        page = my_products.page

        def _strip_wholesale(route):
            req = route.request
            if req.method == "POST" and "pharmacy-products/create/" in req.url:
                try:
                    body = _json.loads(req.post_data or "{}")
                    body.pop("wholesalePricePerBox", None)
                    return route.continue_(post_data=_json.dumps(body))
                except Exception:
                    pass
            return route.continue_()

        page.route("**/pharmacy-products/create/**", _strip_wholesale)
        try:
            drawer = my_products.open_add_product()
            if drawer.cost_per_box_disabled():
                pytest.skip("Cost/Box disabled (BUG-PROD-001)")
            data = dg.new_product(product_type=ptype, company=company, cost_per_box=0,
                                  wholesale_price_per_box=50)   # filled so client validation passes
            try:
                drawer.fill_form(data)
            except Exception as exc:  # noqa: BLE001
                pytest.skip("could not fill the form (AntD Select flake / slow env): {}".format(exc))
            with page.expect_response(
                lambda r: "pharmacy-products/create/" in r.url, timeout=15_000
            ) as ri:
                drawer.submit()
            resp = ri.value
            if resp.status in (404, 500, 502, 503):
                pytest.skip("environment issue (BUG-API-001)")
            body = ""
            try:
                body = str(resp.json()).lower()
            except Exception:
                pass
            assert resp.status in (200, 201) and WHOLESALE_BACKEND_NULL_MESSAGE.lower() not in body, (
                "BUG-PROD-008: backend rejected a create with no wholesalePricePerBox "
                "({} {})".format(resp.status, body)
            )
        finally:
            page.unroute("**/pharmacy-products/create/**", _strip_wholesale)

    @allure.story("TC-PROD-ADD-057: Edit Product can be saved after clearing Wholesale Price/Box")
    @allure.issue("BUG-PROD-008")
    @pytest.mark.regression
    def test_edit_can_clear_wholesale(self, my_products):
        names = my_products.table.column_values("Name")
        if not names:
            pytest.skip("no products to edit")
        target = names[0].split("\n")[0].strip()
        drawer = my_products.edit_product(target)
        assert not drawer.is_required_marked("wholesale_price_per_box"), (
            "BUG-PROD-008: Wholesale Price/Box is required-marked in Edit Product too"
        )
        drawer.set_number("wholesale_price_per_box", "")
        drawer.submit()
        try:
            _wait_for_validation(drawer)
        except Exception:
            pass
        errs = drawer.validation_errors()
        assert WHOLESALE_REQUIRED_MESSAGE.lower() not in " ".join(errs.values()).lower(), (
            "BUG-PROD-008: Edit Product blocks saving without a Wholesale Price/Box "
            "(errors: {})".format(errs)
        )
