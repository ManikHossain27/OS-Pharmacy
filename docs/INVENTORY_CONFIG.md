# Inventory Config (Settings > Inventory Config)

Route `/settings/inventory-config`. Two required fields per pharmacy: **VAT Percentage** (default 17.4, drives TP/VAT mode:
VAT/Box = TP x %) and **Opening Stock Percentage** (default 12, drives Opening Stock mode: BTP+VAT/Box = Retail x (1 - %)).

Tests: `tests/inventory/config_module/` (118 tests, page object `pages/inventory_config_page.py`). Page tests run in QA Ret Pharma A,
effect tests in QA Ret Pharma B; every test restores 17.4 / 12.

| Area | Result |
|---|---|
| Page: defaults, save, persist, Cancel, tidy input, validation, scope | 56 / 57 pass |
| Double-click Save sends 2 requests | BUG-INV-056 (Low) |
| TP/VAT effect (label, preload, typed TP, created inventory, old inventory) | all pass |
| Opening Stock effect (default %, BTP, override, created inventory, old inventory) | all pass |

Verdict: the configuration works correctly; only the double-click guard on Save is missing.
