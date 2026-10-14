"""Cart behaviour that is identical in every inventory mode (spec sections 27-34).

``CartContentsCases`` holds the cases every mode has; ``SpecialLineCartCases`` adds the Special Discount cell case for
the modes whose ``CART_SHAPES`` contain ``special_line_with_plain``.  A mode's ``TestCartContents`` inherits them and
supplies ``SHAPES``, ``HEADERS`` / ``ABSENT_HEADERS``, its assertion helpers ``VERIFIER`` / ``CHECK_CART`` and, when
its create form needs a price to add a line, ``LINE_PRICE``.  The classes are not named ``Test*`` so pytest collects the cases once per mode.
"""
from __future__ import annotations

import allure

from utils.inventory_scenarios import LineSpec, Scenario


class CartContentsCases:
    SHAPES: dict
    HEADERS: tuple[str, ...]
    ABSENT_HEADERS: tuple[str, ...]
    VERIFIER: type                 # the mode's Verifier
    CHECK_CART = None              # staticmethod(<the mode's check_cart>)
    LINE_PRICE: dict = {}          # extra LineSpec fields a line needs in this mode (Default: btp_vat_per_box)

    def _scenario(self, shape: str) -> Scenario:
        return Scenario(id=shape, lines=self.SHAPES[shape])

    def _check_shape(self, v, j) -> None:
        """Mode-specific checks on a filled cart, added to the common cart verification."""

    def _verify_cart(self, flow, shape: str, label: str) -> None:
        inv = flow.inventory
        j = flow.fill_cart(self._scenario(shape))
        v = self.VERIFIER(f"cart [{label}]")
        self.CHECK_CART(v, inv.cart_rows(), j.lines, inv.cart_total_price(), inv.total_items(), j.specs)
        self._check_shape(v, j)
        v.assert_all()

    # ------------------------------------------------------------------ contents
    def pytest_generate_tests(self, metafunc) -> None:
        """Parametrise ``shape`` with the mode's own cart shapes."""
        if "shape" in metafunc.fixturenames:
            metafunc.parametrize("shape", list(self.SHAPES))

    @allure.story("Every cart shape displays the correct line values, Total Items and Total Price")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cart_matches_oracle(self, flow, shape):
        self._verify_cart(flow, shape, shape)

    @allure.story("Cart column headers follow the mode (spec 10 / 29)")
    def test_cart_headers(self, flow):
        flow.fill_cart(self._scenario("single_plain"))
        headers = [h for h in flow.inventory.cart.headers() if h]
        for col in self.HEADERS:
            assert col in headers, f"cart column {col!r} missing; got {headers}"
        for col in self.ABSENT_HEADERS:
            assert col not in headers, f"cart column {col!r} must not be shown in this mode; got {headers}"

    @allure.story("Business rule: a product can be in the cart ONCE only - a second add is refused with a message")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_same_product_cannot_be_added_twice(self, flow):
        inv = flow.inventory
        added1, _ = inv.try_add_line(LineSpec("P0", box_qty=2, **self.LINE_PRICE), flow.next_batch())
        assert added1 and inv.total_items() == 1
        added2, msgs = inv.try_add_line(LineSpec("P0", box_qty=5, **self.LINE_PRICE), flow.next_batch())
        assert not added2 and inv.total_items() == 1 and inv.cart_row_count() == 1, "duplicate product was added"
        assert any("already in the cart" in m.lower() for m in msgs), f"no 'already in the cart' message; messages={msgs}"
        assert "2" in inv.cart_rows()[0]["Box Qty"], "the original line must be unchanged by the refused add"

    @allure.story("Different products can all be added (one line each)")
    def test_different_products_all_added(self, flow):
        j = flow.fill_cart(self._scenario("three_plain_free_plain"))
        assert flow.inventory.total_items() == 3 and len({l.name for l in j.lines}) == 3

    @allure.story("Deleting the only line empties the cart")
    def test_delete_line(self, flow):
        inv = flow.inventory
        flow.fill_cart(self._scenario("single_plain"))
        inv.delete_cart_row(inv.cart_row(0))
        assert inv.cart_row_count() == 0 and inv.total_items() == 0

    @allure.story("Large Box Qty and fractional prices render without truncation")
    def test_large_and_decimal_values(self, flow):
        self._verify_cart(flow, "large_qty_with_expiry", "large")


class SpecialLineCartCases:
    """Modes whose shapes include ``special_line_with_plain``: the Special Discount cell."""
    SHAPES: dict

    @allure.story("A line with Special Discount shows 'SP.Dis' in the Discount column; others show '-'")
    def test_special_discount_cell(self, flow):
        flow.fill_cart(Scenario(id="special", lines=self.SHAPES["special_line_with_plain"]))
        rows = flow.inventory.cart_rows()
        assert "SP.Dis" in rows[0]["Discount"] and rows[1]["Discount"].strip() == "-", [r["Discount"] for r in rows]
