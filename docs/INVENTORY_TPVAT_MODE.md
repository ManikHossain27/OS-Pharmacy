# Inventory - TP/VAT mode: workbook review + test suite

Source of truth: sheet **`TP per vat mode (2)`** of `Knowledge/Inventory Management/PMS_Innventory Calculation (Non Rounded).xlsx`
and sections 10-13, 38-41 of `Knowledge/Inventory Management/Inventory Management.md`.

## 1. Workbook logic (`TP per vat mode (2)`)

Recomputed with a formula engine on 60-400 random products across 11 scenarios (`tools/validate_tpvat_oracle.py`):
**23,210 cell comparisons, 0 mismatches** against the Python oracle (`utils/tpvat_calc.py`).

| Rule | Cells | Verdict |
|---|---|---|
| VAT/Box = ROUND(TP/Box x 17.4 %, 2) unless typed (form pre-fills; editing TP re-derives it) | H, G1 | matches the app |
| Line total price = TP x Box + VAT x Box **+ VAT/pc x Free pcs** | AC | matches the app (verified live: 60.00 for (15+10) x 2 + 1.00 x 10) |
| Discount base = **TP only**; lines with Free Qty or a Special value are excluded | I3, Q, R | spec 38 |
| Flat discount spread over eligible TP, reduced by the specials first | Q, R | spec 39 |
| Special (manual per-line Tk) overrides % / flat and the free exclusion | S, Q, R | the form field "Special Discount (Tk)" |
| Final Price = ROUND(Total Price - Discount, 0); Round Off shared over **TP after discount** | K2, K3, AA | matches the app (234.80 - 20 = 214.80 -> 215, Round Off 0.20) |
| Purchase price/pc = ((TP+VAT) x Box + VAT/pc x Free - Discount) / (Qty + Free) - Less/Qty + Round share/(Qty+Free) | T | see gaps |
| Supplier Due / Advance = MAX(+/-(balance + Final - Paid), 0) | M3, M4 | see gaps |

### Findings about the sheet / knowledge file (each has a matching test)

| # | Finding | Evidence |
|---|---|---|
| TPVAT-1 | **M3 / M4 do not deduct "Less" (M5)** - the Default sheet was updated to; this one still shows Due/Advance as if Less were paid. | `test_sheet_ignores_less_in_due` |
| TPVAT-2 | **A TP/Box = 0 line makes col T `#VALUE!`**: Less per product (Z) is blank when J = 0 and `"" >= 0` is TRUE. Spec 12/41 says a zero-TP line must still get a purchase price from the available values. | `test_tp_zero_sheet_error`, `test_tp_zero_purchase_price_spec_rule` |
| TPVAT-3 | **Less is allocated by `M5 / K1 x J`**, where K1 = SUM(TP/Box) + SUM(VAT/Box) of the lines (per-box prices, not totals) - mixed units; it is only right by accident. Divided over purchased qty D, not D + Free (same gap as Default). | `validate_tpvat_oracle.py` runs with `less_rule="sheet"`; the UI journeys use `less_rule="total"` |
| TPVAT-4 | **Knowledge file 38/40 example is not what the sheet or the app do**: `(15+10) x 2 / 30 = 1.66` ignores VAT on the 10 free pieces; sheet AC/T and the application both give `60 / 30 = 2.00`. The knowledge file should be corrected. | `test_free_qty_vat_is_charged_on_free_pieces`, `test_knowledge_file_example_needs_free_vat_off` |

## 2. Test suite (`tests/inventory/tp_vat_mode/`)

| Module | Layer | Tests | What it covers |
|---|---|---|---|
| `test_tpvat_calc_oracle.py` | pure (no browser) | 44 | spec examples, workbook sample, ~3,500-combination matrix invariants, 200/300/500-product inventories, sheet gaps, Special, supplier Due/Advance |
| `test_tpvat_form.py` | create form | 47 | structure, VAT auto-calculation (10 TP values), manual VAT keeps TP, qty sync, TP 0 / VAT 0 accepted, free VAT, Special field, duplicate product, Box Qty rules, negatives, expiry, storage |
| `test_tpvat_cart.py` | cart | 17 | 10 cart shapes vs oracle, headers, free-VAT total, duplicate rule, delete, Special cell |
| `test_tpvat_checkout.py` | checkout | 71 | 10 shapes x 4 discounts vs oracle (no data created), TP basis label, % / flat on TP, VAT untouched, Special split, paid / due / advance |
| `test_tpvat_e2e_record_details.py` | e2e | 51 | 40 full journeys -> Inventory Details line by line, Details structure, free VAT, Special, Due & Buy / Less & Buy / Advance & Buy with supplier balance, record list |

Design: same page objects (`pages/`), flow facade (`TpVatFlow`), oracle (`utils/tpvat_calc.py`), assertions
(`utils/tpvat_assertions.py`) and scenarios (`utils/tpvat_scenarios.py`); no selectors in tests.
Run: `pytest tests/inventory/tp_vat_mode -m calc` (offline) or `-m "not calc"` (needs the portal).

## 3. TP/VAT screens (verified live 2026-10-11)

* Form: TP/Box + VAT/Box (label "VAT/Box (17.4%)"), plus **Special Discount (Tk)** (`#specialDiscountValue`, also in Default mode).
* Cart / checkout rows: Details | Box Qty | TP/Box | VAT/Box | Discount | Total Price | Exp date | Free; the Discount cell of a special line is `Tk 20.00 / SP.Dis / 10.00%` (% of TP).
* Checkout / Details summary: Total Items | Total Price (TP+VAT) | Total TP | Total VAT | General Discount (on TP) | Special Discount | Round Off | Final Price | Total Paid | Due (Details: Inventory Mode "TP/VAT", Payment Status).
* Details item columns: Details | Batch / Expiry | Rack No | Qty | Qty/Box | TP | VAT | Discount | Purchase Price | Retail | Wholesale | Margin | Price (Total / Final).
* Special discount field applies to **Default mode too** - the earlier note "no entry field found" in the Default-mode findings was wrong.

Total: **230 tests** (44 offline + 186 live; the live layer creates ~50 real inventories in the e2e module).
