# Inventory Return - test suite

Suite: `tests/inventory/return_module/` (page objects in `pages/inventory_return_page.py`).
Run (headed, serial): `python -m pytest tests/inventory/return_module --headed-run -p no:cacheprovider`.

## Rules the suite verifies (product-owner answers)

- A return is priced at the batch purchase price: the line's final cost (after discount and round-off) / total pieces, x quantity. A box return converts to pieces.
- A return can go to **any** supplier; that supplier's balance changes by the **Final Price** (return total - demurrage, rounded to whole Taka).
- Demurrage (% or Tk) is the business loss: it reduces the Final Price credited to the supplier and to the Pharmacy Wallet (Total Treasury). Over 100 %, negative, and flat demurrage above the total are blocked; blank = 0.
- The supplier is not pre-selected on the Return Checkout.
- A return with Final Price 0 is not accepted. Adding the same batch twice replaces the first line. Free pieces return at the batch purchase price.
- After a return the record becomes returned partially or fully.
- Returning from an Inventory Record pre-loads that inventory's remaining lines; Company, Product and Batch are locked.

## Files

| File | Tests | Covers |
|---|---|---|
| `test_return_form.py` | 89 | selection, Return Qty validation, cart maths (pc/box), cart edit/delete, checkout panel, demurrage preview |
| `test_return_complete.py` | 33 | completed returns (single/multi product, pc/box, demurrage, invoice/note, rounding), wallet, second supplier, 100 % demurrage, cancel return |
| `test_return_from_record.py` | 29 | pre-loaded cart, locked selectors, partial/full/remainder returns, other supplier, Free Qty, Cancelled inventory, stale tab, TP/VAT and Opening Stock |
| `test_return_record.py` | 16 | list, tiles, Details, row menu, supplier / status / text filters, Reset |
| `test_return_extra.py` | 24 | balance signs (zero / Advance supplier), several batches of one product, menu returns on TP/VAT and Opening Stock, cancel after changes, repeat full return, 2.5 pc page-crash probe, Return Record date range, pagination and combined filters |
| `test_return_product_stock.py` | 15 | the product's available quantity (Product List Stock Status, pieces and boxes) after returns, cancels, failed returns, double-click, and record returns |
| `test_return_advance.py` | 8 | returns to a supplier already in Advance: preview, complete, cancel, from a record |
| `test_return_payment.py` | 23 | records bought half-paid / unpaid / discounted / with Free Qty / with expiry: cart price, full return, free pieces |
| `test_return_after_edit.py` | 6 | return after Edit Inventory: price up/down, retail/wholesale, quantity + price, two edits |
| `test_return_sales.py` | 12 | interplay with Sale: only the available quantity is returnable, from the menu and from a record |
| `test_return_inputs.py` | 16 | invoice / note text, reload, Back, unknown inventory id, two tabs returning the same stock |

Extra suites run on three pharmacies in parallel (own login each): Manik Pharma (Advance supplier `QA Ret Zero 10242256`, paid purchases), QA Ret Pharma A and B (new, no Cash balance, so purchases on credit; set up with `tools/setup_return_pharmacy.py`). Env: `PHARMACY_NAME`, `QA_PRODUCTS`, `QA_SUPPLIER`, `QA_ADVANCE_SUPPLIER`, `QA_NO_CASH`, `AUTH_STATE`.

Creating an inventory takes about 5 minutes on staging, so menu-return tests share a persisted "pool" inventory (`logs/return_pool.json`) and assert deltas (batch stock, supplier balance, Return Record, tiles). Tests that consume stock create their own inventory.

## Results (2026-10-25)

Full run: every failure maps to a bug below. Product-quantity checks (TC-INV-RET-42..46) all pass: the Product List total follows every return, cancel and record return. Form tests: 93 of 104 (with product stock) pass; the rest are BUG-INV-041/053. The pool's first batch was enlarged to 20,000 pieces after it ran dry mid-run. Second pass (2026-10-25): Advance supplier, purchase terms, after-edit, sales interplay, text fields and navigation - 62 more tests, every failure maps to BUG-INV-043 / 050 / 054 / 055. Catalog: TC-INV-RET-01..61.

## Findings

| Bug | Severity | Summary |
|---|---|---|
| BUG-INV-043 | Critical | The supplier chosen at checkout is ignored; the return is recorded against and credited to the inventory's original supplier |
| BUG-INV-055 | High | After everything was sold, Return Inventory from the record still offers the full quantity |
| BUG-INV-054 | Low | An unknown inventoryId leaves the Return form with a disabled Product select and no message |
| BUG-INV-053 | Medium | A flat (Tk) demurrage above the return total is accepted (Final Price 0) |
| BUG-INV-052 | High | Typing 2.5 pc and pressing Add to Return Cart blanks the page |
| BUG-INV-051 | High | A double-click on Complete creates two returns |
| BUG-INV-047 | High | Return Inventory on a fully returned inventory pre-loads the full original quantities |
| BUG-INV-048 | High | Return Inventory on a Cancelled inventory pre-loads full quantities |
| BUG-INV-045 | High | A Cancelled return still offers Cancel Return |
| BUG-INV-041 | Medium | Return Qty 0 / negative / box fraction is silently changed to 1 and added |
| BUG-INV-044 | Medium | A return with Final Price 0 must be refused (product owner); it is not blocked and fails with HTTP 500 |
| BUG-INV-046 | Medium | Inventory Record status stays Paid after a partial return |
| BUG-INV-050 | Medium | Return from a record does not offer the Free Qty pieces (all pieces return at the batch purchase price) |
| BUG-INV-042 | - | Closed: adding the same batch again replaces the first line is intended |
| BUG-INV-049 | Low | Return Record "All staff" filter lists no staff |
| Known | - | BUG-INV-022 (Details line items 0 box / 0 pc), 026 (Cancel popover off-screen), 027 (tiles count cancelled returns), 028 (wallet not credited) |

## Limits

- The '100%' pool product cannot be found by name on the Product List (not investigated), so product-total checks use two of the three pool products. The Return form's batch list is virtual, so the total is compared as a lower bound.
- The server does refuse a second full return of a returned inventory (only the cart reload, BUG-INV-047, is wrong).
- A supplier already in Advance could not be set up while BUG-INV-043 credits the wrong supplier (TC-INV-RET-34 Blocked).
- User permissions are out of scope (one staff login). The new pharmacies have no Cash balance (Additional Balance did not credit it), so paid purchases run on Manik Pharma only.
- Sales interplay and stock adjustments are out of scope.
