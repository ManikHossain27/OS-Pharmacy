# Inventory Record list - test suite

Source: section 43 (Inventory Record) and 44.1 (Details link) of `Knowledge/Inventory Management/Inventory Management.md`.

Suite: `tests/inventory/record_module/` (27 tests). Read-only - it never creates inventory.
Serial, headed: `pytest tests/inventory/record_module --headed-run`.

| Area | Verified behaviour |
|---|---|
| Layout | Summary tiles (Total Inventory (N), Paid, Due, Discount with Tk amounts), the five filters, Reset Filters, the nine columns |
| Filters | Type options and results, Status results, Supplier, combined Type + Supplier, search with no match, Reset Filters |
| Date range | A single-day range lists only that day; the inputs show the applied range |
| Paging | Page sizes 10/20/50/100, `Showing a-b of N`, Next/Previous, every page unique and newest first |
| Row content | ID / date / type / item-count format, Status agrees with Bill and Paid amounts, discount badge wording |
| Details link | The details action opens the same inventory ID as the clicked row |

## How the suite scopes its data

The list is limited to **today** by default (the request carries `from` / `to`) and today often has no records.
Tests that need data use the `record_all` fixture, which sets a year-to-date Date Range (`YYYY-MM-DD` typed into
the picker). Layout, the Date Range test and the search test use the default scope.

## Findings

| ID | Severity | Status | Summary |
|---|---|---|---|
| BUG-INV-034 | High | Open | Status = Paid / Due / Advance: list request returns HTTP 400 (`status should be of type java.util.Optional`), UI shows the empty state. Returned / Cancelled work. 3 tests stay red. |
| BUG-INV-035 | Medium | Not reproducible 2026-10-13 | On 2026-10-12 the Type filter offered Missing / Destroyed and ignored them. Now only Purchase and Borrowed are offered (matches the spec). |
| BUG-INV-039 | Low | Open | The list is limited to today but the Date Range inputs are blank (`test_applied_range_is_visible` stays red). Confirmed as a bug. |

## Test assumptions corrected during the live runs

* Inventory numbers restart every day (`#INV_yyyymmdd_n`), so "newest first" is ordered by (day, n).
* Reset Filters also resets the Date Range to today.
* An AntD dropdown that is closing still matches `:visible`; the page object waits for the open dropdown only.
* The Status cell can hold two lines (`Advance` / `Tk 250`); the first line is the status.

## Live results (2026-10-13, staging)

23 passed, 4 failed (3 for BUG-INV-034, 1 date-range observation) of 27.
