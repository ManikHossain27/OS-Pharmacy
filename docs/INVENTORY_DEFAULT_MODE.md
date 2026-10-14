# Inventory - Default mode: workbook review + test suite

## 1. Workbook logic review (`Default Mode (2)`)

Recomputed with a formula engine on 60 and 400 random products across 9 discount scenarios
(`tools/validate_inventory_oracle.py`): **39,645 cell comparisons, 0 mismatches** against the
Python oracle (`utils/inventory_calc.py`). The core maths is correct:

| Rule | Cells | Verdict |
|---|---|---|
| Total Qty = Box x Qty/Box; Total BTP+VAT = BTP+VAT/Box x Box | D, G | correct |
| Discount base excludes Free-Qty lines (and lines with a manual "Special" discount) | I4, N, O | correct |
| Flat discount spread proportionally to BTP+VAT over eligible lines | N, O | correct, sums exactly to the flat amount |
| Final Price = ROUND(Total - Discount); rounding share pushed into each line | K4, I1, X | correct, line costs reconcile to Final Price |
| Purchase price/pc = (G - discount) / (Qty + Free) | Q | correct (matches spec 38/40 examples) |

Edge cases in the **sheet itself** (locked by `TestWorkbookEdgeCases`, each has a matching app check):

1. **BTP+VAT/Box = 0** -> `Q` becomes `#VALUE!` (blank `W` compares `>= 0`). Spec 41 allows zero-cost lines. *(Box Qty 0 / Qty-per-Box <= 0 is no longer an error: column Q now returns blank - fixed in the 2026-10-08 workbook.)*
2. **Flat discount > eligible total** is not capped -> negative Final Price.
3. **Flat discount with only Free-Qty lines** is silently dropped (discount 0).
4. **"Less" (col W)** is spread over purchased qty `D`, while every other term uses `D + Free`.
5. Final Price is whole-unit rounded - **confirmed by the user as required**; checkout and Inventory Details are asserted exactly against the rounded value.

## 2. Test suite (`tests/inventory/default_mode/`)

| Module | Layer | What it covers |
|---|---|---|
| `test_default_calc_oracle.py` | pure (no browser) | spec examples, workbook anchors, ~2,000-combination matrix invariants, 200/300/500-product inventories, sheet edge cases, **Special (col P) per-line discount** (override, base exclusion, flat reduced by specials, free-line interaction, uncapped) |
| `test_default_form.py` | create form | structure, per-mode panel state, product defaults, qty and BTP+VAT sync (both directions, fractional), every validation, storage, expiry, barcode |
| `test_default_cart.py` | cart | 10 cart shapes vs oracle, headers, edit-in-place, delete, expanded view, hold/resume |
| `test_default_checkout.py` | checkout | 10 shapes x 4 discounts vs oracle (no data created), discount rules, payment/due, supplier, types |
| `test_default_e2e_record_details.py` | e2e | 40 full journeys (create -> cart -> checkout -> complete -> Inventory Details, line matched by unique batch), payment variants, success modal, stock increase, preload, Borrow, double-click, flat-discount failure |

Design: Page Objects (`pages/`) + components (`components/`) + business-flow facade
(`pages/inventory_flow.py`) + oracle/assertion libraries (`utils/`); no selectors in tests.
Run: `pytest tests/inventory/default_mode -m calc` (fast, offline) or `-m "not calc"` (needs the portal).

## 3. Status of this run

* `calc` layer: **41 passed** (offline).
* UI layers (210 tests): written and collected, **not yet executed live** - the staging portal
  dropped "Manik Pharma" from the pharmacy picker (BUG-API-001) and page loads timed out, and
  the Playwright MCP server failed to connect. Selectors/cell expectations that were not already
  proven by earlier runs (e.g. exact Inventory Details column wording, expanded-cart headers)
  need a first live pass.

## 4. Business rules confirmed by the user (2026-10-07)

* **A product can be in the cart only once.** A second add is refused with the toast
  "This product is already in the cart". The spec (`Knowledge/Inventory Management/Inventory Management.md`
  sections 2, 25, 28, 46, 47.9) was updated; the matrix now has 8 cart shapes x 4 discounts = 32 journeys,
  and `test_default_cart.py` / `test_default_form.py` assert the refusal, that the cart is unchanged, and that a
  deleted product can be added again.
* **Final Price is rounded** (sheet K4); the app shows the difference as "Round Off".
* Verified live: Inventory Details is a **page** (`/inventory-record/details/<id>`) with Inventory Mode,
  General/Special Discount, Round Off, Margin and Price (Total / Final) columns; per the user, Min. Qty and Barcode are NOT required there and Total Price is the "Total:" label in the Price
  column; Free Qty is shown in the Qty column as "N pc free" and is checked there.
* **Round Off allocation (confirmed by the user, 2026-10-08):** the rounding difference is shared between lines in
  proportion to each line's **after-discount** amount (the application's rule). The workbook's column X shares it by the
  **pre-discount** BTP+VAT, so the sheet and the app give slightly different per-line Purchase Price / Margin / line cost when
  some lines are discounted and others are not (e.g. a free-qty line next to a discounted line). The oracle follows the
  application; `round_basis="pre_discount"` reproduces the sheet for `tools/validate_inventory_oracle.py`. The workbook
  formula in col X (and Q / R / S-V / Y, which use it) should be updated if the sheet must match the app.

### Workbook update 2026-10-08 (user edited `Default Mode (2)`)

Mirrored in `utils/inventory_calc.py` and re-validated cell by cell (`tools/validate_inventory_oracle.py`, 7,870 comparisons, 0 mismatches):

| Cell | Change |
|---|---|
| X (Round Adj/product) | now `I1 / (K3 - K2) x (G - O)` - Round Off shared by **after-discount** amount, same as the app |
| Q (Purchase Price/pc) | new guard: blank when Box Qty is 0/blank or Qty/Box <= 0 (a free-only line no longer errors) |
| M3 / M4 (Supplier Due / Advance) | "Less" (M5) is now deducted: `M2 + K4 - K5 - M5` |
| Z (new) | `Total Price` per line (G, only when Box Qty > 0) with total in Z5 - display only |

The oracle's `round_basis="pre_discount"` option (the old col X rule) is kept for reference only.

### Correction (2026-10-08) - negative input
An earlier run reported "negative Box Qty / Free Qty / price accepted". That was a **test artefact**: Playwright `fill()` writes
straight into the input. Typed with the real keyboard, every numeric field **clamps a negative to 0** (no error message), so a negative
value never reaches the cart. The one real finding is **Box Qty = 0**, which adds a 0-box / Tk 0.00 line - open question whether that is
valid (the workbook now tolerates Box Qty 0, so a free-only line may be intended). Use `InventoryPage.type_value()` for any test where
the typed characters matter.

### Business rules confirmed 2026-10-08 (product owner)
* **Past Expiry Dates are allowed** (intentional) - BUG-INV-014 closed as not a defect.
* **Storage "WHS" has no input** (a pharmacy has one warehouse) - BUG-INV-010 closed as not a defect.
* **Box Qty must be greater than 0.** The app accepts 0 -> logged as **BUG-INV-030** (Medium).

### Due & Buy / Less & Buy / Advance & Buy (verified live 2026-10-11)
Complete Inventory with **Total Paid != Final Price** opens a decision dialog; the inventory is created only after a button is chosen.

| Paid vs bill | Dialog | Buttons | Effect |
|---|---|---|---|
| less | "You paid less than the bill" (BILL / YOU PAID / SHORT BY) | **Due & Buy** | the short amount stays Due to the supplier (pay later) |
| less | | **Less & Buy** | the short amount is waived: the owner does not pay it, **products cost less** |
| more | "You paid more than the bill" (BILL / YOU PAID / EXTRA) | **Advance & Buy** | the extra becomes an Advance with the supplier |
| equal | none | - | created directly |

Supplier balance (Supplier List, signed: + due / - advance) follows workbook M2-M5 in every journey tested:
`after = before + Final - Paid - Less` (Less = Final - Paid for Less & Buy, so the balance does not move).

Less & Buy specifics (app, confirmed from Inventory Details):
* Less share per line = `Less / Total Price x line BTP+VAT` (workbook col W); shown in the Discount cell as **"Less Tk x"**.
* Details pricing breakdown has a **Less** row: Total Price - General - Special - **Less** + Round Off = Final Price (= the amount paid); the status becomes **Paid**; Advance & Buy shows **Advance**.
* Line cost = `BTP+VAT - discount - Less share + round share`, spread over **Qty + Free Qty**.
  **Workbook gap 5 (confirmed against the app):** col Q divides W by `D` (purchased qty) only, so a line with Free Qty is
  over-reduced; the app divides by `D + E`. Fix: `-IF(W8>=0, W8/(D8+E8), 0)` in col Q. The oracle follows the app
  (`less_basis="physical"`); `less_basis="purchased"` reproduces the sheet for the validator.
* Findings: BUG-INV-031 (status 'Advance' on an unpaid Due & Buy invoice), BUG-INV-032 (fractional Paid is rounded - **intentional, closed 2026-10-11**),
  BUG-INV-033 ("no Less row" - **retracted 2026-10-11: the row exists; logged in error**).

* **Total Paid is rounded to a whole taka** (112.7 -> 113, 67.5 -> 68) - intentional, confirmed 2026-10-11.
