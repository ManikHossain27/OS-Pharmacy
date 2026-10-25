# Edit Inventory - test suite

Source: the Inventory Record row menu (spec section 43) and the create flow's rules (spec 27-44.1) applied to an
existing record. The spec has no dedicated Edit Inventory section, so a figure that differs from the create-flow rule
is reported as a finding.

Suite: `tests/inventory/edit_module/` (about 300 tests across `test_edit_inventory.py`, `test_edit_modes.py`, `test_edit_matrix.py`, `test_edit_combinations.py`, `test_edit_actions.py`, `test_edit_mode_parity.py`). Serial, headed: `pytest tests/inventory/edit_module --headed-run`.
Every test creates its own two-line inventory (Default, TP/VAT or Opening Stock; paid, due, advance, borrowed or discounted as the case needs) (`create` / `saved` fixtures) and edits that one, so
shared data is never touched.

## The flow

| Step | Route / control |
|---|---|
| Open | Inventory Record > row kebab > **Edit Inventory** > `/inventory/edit/<id>` (the Inventory form and cart, pre-loaded) |
| Edit a line | Pencil on the cart row > the form > Save Changes |
| Checkout | **Go to Inventory Checkout** > `/inventory/edit/checkout/<id>` (same summary, payment dialog and Edit Cart) |
| Save | **Update Inventory** > `PUT /api/1.0.0/secured/inventories/update/<id>/<pharmacy>` |
| History | Row kebab > **Inventory Edit History** (Total Changes, date, `Edit by <user>`) |

Page objects: `pages/inventory_edit_page.py` (`InventoryEditPage`), `InventoryRecordPage.open_row_menu / choose_row_action
/ open_details_for`. Helpers: `tests/inventory/edit_module/helpers.py`.

## Coverage

| Area | Tests |
|---|---|
| Entry and preload | row menu, edit page title, cart pre-loaded, line form pre-loaded |
| Line fields | retail, wholesale, Min Qty, Rack, Free Qty, Qty/Box, BTP+VAT/Box persist after Update; reprice flows to the Record; Batch No; duplicate Batch No refused; Expiry; Box Qty 1000; both lines |
| Cart structure | Box Qty change, delete line, add product, duplicate product refused, empty cart blocked, Box Qty 0 |
| Checkout and discount | supplier and type kept, totals follow the cart, saved discount pre-loaded, removed, added, flat Tk |
| Update and payment | no change, paid in full, Details show the line, Due & Buy, pay nothing, Less & Buy, Advance & Buy, BANK / CARD / MFS, dialog amounts |
| Starting states | Due, Advance, Borrowed, Free Qty records |
| Supplier and type | supplier balance follows the edit, Invoice Number persisted, supplier change (skipped: one supplier), type read-only |
| History and navigation | none / one / two entries, abandoned edit, Edit Cart round trip, Cancelled record not editable |
| Combination matrix (`test_edit_combinations.py`, 146) | starting state (paid, due, advance, borrowed, nothing paid, discounted) x edit (Box Qty up / down, delete a line) x payment outcome (keep, full, half, zero, over, less): Default 57, TP/VAT 26, Opening Stock 26; saved x new discount (18); payment method x outcome (12); combined changes (7) |
| Effects of an edit (`test_edit_actions.py`) | Return cart follows the edit, supplier not pre-selected on Return, Returned record, Cancel restores the supplier balance and keeps history, Pay Due dialog shows the edited Due, repeated edits, history user and date, supplier change across two suppliers (all modes), two tabs |
| Mode parity (`test_edit_mode_parity.py`) | TP/VAT and Opening Stock repeat the line-field, cart, checkout, history and navigation checks; TP/VAT TP/VAT edits; Opening Stock percent, manual BTP and Retail re-derive |
| Other modes (`test_edit_modes.py`) | TP/VAT and Opening Stock: edit route and mode badge, cart pre-loaded, Box Qty reprices the line, Update matches the checkout Final Price, mode kept |

## Findings

| ID | Severity | Status | Summary |
|---|---|---|---|
| BUG-INV-030 | Medium | Open (extended) | Box Qty 0 is accepted when editing a line, as on create |
| BUG-INV-036 | High | Open | A Cancelled inventory still offers Edit Inventory / Pay Due / Return / Cancel and the edit screen opens |
| BUG-INV-037 | Medium | Open | Inventory Type is editable in the edit checkout but the server refuses it (HTTP 400) |
| BUG-INV-038 | Medium | Open | The edit checkout pre-fills Total Paid with the NEW Final Price, not the amount originally paid (confirmed expected behaviour: original paid amount) |
| BUG-INV-039 | Low | Open | Blank Date Range inputs on the Inventory Record list |
| BUG-INV-040 | High | Open | A fully Returned inventory still offers Edit Inventory / Pay Due / Return / Cancel |

BUG-INV-030, -036 and -037 are also reproduced in TP/VAT and Opening Stock.

Open question: after a Retail Price change on the Opening Stock edit screen the cart total does not change (`test_retail_price_rederives_btp`); the create screen re-derives BTP+VAT/Box. Awaiting product-owner confirmation.

## Limits

* Stock is not observable in the UI (C. Stock shows "-"), so stock changes after an edit are not tested.
* Pay Due needs an SMS OTP, so only the dialog (the edited Due) is checked.
* Two suppliers are used: "QA Edit Supplier" and "QA Edit Supplier B" (added by the `other_supplier` fixture when missing). The first sorts first in the list.
* The edit checkout's 401 after a very long run is a session expiry, not a product defect.

## Environment notes

* Payments use CASH. On 2026-10-13 the CASH account was overdrawn (-148 243) and every create / update returned HTTP 400
  "insufficient balance"; the suite passed once the payment accounts were topped up.
* A create plus an edit takes 5-7 minutes on staging, so the full suite runs for about 4 hours.

## Live results (2026-10-14, staging)

Default mode: 55 passed, 3 failed for product bugs (BUG-INV-030, BUG-INV-036, BUG-INV-037), 1 skipped.
TP/VAT and Opening Stock: 10 of 10 passed.
The TP/VAT and Opening Stock edit routes carry a mode segment (`/inventory/<mode>/edit/<id>`); the page object matches both.

## Live results (2026-10-22 to 2026-10-25, staging)

Matrix, actions and mode parity (244 tests): 236 passed; 7 failed for product bugs (BUG-INV-030 x2, BUG-INV-036 x2, BUG-INV-037 x2, BUG-INV-040) and 1 open question (Retail re-derive). A 20-hour run is cut by session expiry (HTTP 401), so run it in chunks.
