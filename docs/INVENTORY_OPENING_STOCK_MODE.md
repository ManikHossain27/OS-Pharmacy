# Inventory - Opening Stock mode: workbook review + test suite

Source of truth: sheet **`Opening Stock`** of `Knowledge/Inventory Management/PMS_Innventory Calculation (Non Rounded).xlsx`
(corrected by the product owner on 2026-10-12) and sections 14-21 of `Knowledge/Inventory Management/Inventory Management.md`.

## 1. Workbook logic

Recomputed with a formula engine on 60 random products across 10 scenarios (`tools/validate_opening_oracle.py 60 7`):
**8,470 cell comparisons, 0 mismatches** against the Python oracle (`utils/opening_calc.py`), using the workbook as it is.

| Rule | Verdict |
|---|---|
| BTP+VAT/Box = ROUND(Retail x (1 - %/100), 2); default % = 12; % clamped to 0..100 | matches the app (live 2026-10-12) |
| Editing Retail or % re-derives BTP+VAT/Box; editing Total sets BTP/Box = Total / Box Qty | matches the app |
| A manual BTP+VAT/Box does **not** back-calculate the %; a later Retail edit re-derives BTP+VAT/Box | **accepted behaviour** (product owner, 2026-10-12) - BUG-INV-005 / BUG-INV-006 closed as "Not a Bug" |
| I8 is a typed constant while F8 holds 15 % | **intentional** - shows that a manual BTP overrides the % column |
| After BTP+VAT/Box everything is the Default-mode calculation (`utils.inventory_calc`) | matches |
| Supplier Due / Advance = balance + Final - Paid - Less | the sheet (N3/N4) now deducts Less, as the app does |
| Discount columns O/P read `$J$2:$J$4` on every product row | corrected in the sheet |

## 2. Application defects

| ID | Summary | Status |
|---|---|---|
| BUG-INV-030 | A line with Box Qty 0 is accepted into the cart (Default and Opening Stock modes) | Open |
| BUG-INV-001 / 031 | Discount / supplier-advance netting defects shared with Default mode | Open |

## 3. Suite - `tests/inventory/opening_stock_mode/`

| File | Scope |
|---|---|
| `test_opening_calc_oracle.py` | pure oracle vs workbook rules (48) |
| `test_opening_form.py` | create form: derivation, clamps, manual BTP, validation |
| `test_opening_cart.py` | 10 cart shapes row by row against the oracle |
| `test_opening_checkout.py` | 40 cart x discount combinations + behaviour (no stock created) |
| `test_opening_e2e_record_details.py` | 40 journeys create -> cart -> checkout -> Complete -> Record -> Details; payment dialog; Due/Less/Advance & Buy |

Run (serial only, headed): `pytest tests/inventory/opening_stock_mode --headed-run`.

## 4. Live results (2026-10-12, staging, headed)

| Run | Result |
|---|---|
| Cart + checkout special-discount cases | 23 passed |
| E2E module (first run) | 56 passed, 3 failed: two were a number-parser bug (negative wholesale margins lost their sign, fixed), one a record-list timeout |
| Re-run of those 3 journeys (+ 2 related) | 5 passed |
| Create-form module (61 tests, after the 005/006 decision) | 59 passed, 2 failed = BUG-INV-030 (Box Qty 0 with Free Qty 0 and 5 is added to the cart) |
