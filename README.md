# PMS SQL Portal — QA & Playwright Automation

End-to-end SQA assessment **and** an industry-standard Playwright/Pytest
automation framework for the Product and Customization modules of
**PMS SQL Portal** (`https://pms-sql-portal.ems24.co/`), scoped to the
**Manik Pharma** pharmacy.

---

## 1. Deliverables in this repo

| Deliverable | Location |
|---|---|
| Manual test report (Test Summary / Test Cases / Bug Logs) | `PMS_Product_Module_Test_Report.xlsx` |
| QA task report (narrative) | `docs/QA_TASK_REPORT.md` |
| Automation framework | `config/`, `pages/`, `components/`, `tests/`, `utils/`, `conftest.py` |
| Test-case catalog (source of the Excel) | `tools/test_case_catalog.py` |
| Bug data (source of the Bug Logs sheet) | `test_data/bug_logs.json` |
| Evidence | `screenshots/` |

Regenerate the workbook after editing the catalog / bug JSON:

```bash
python tools/build_excel_report.py
```

---

## 2. Project structure

```
OS Pharmacy/
├── .env / .env.example / .gitignore
├── requirements.txt / pytest.ini / conftest.py
├── config/            # settings + per-environment config
│   ├── settings.py        # typed singleton, loads .env
│   └── environments.py    # local / staging / prod base URLs + guards
├── pages/             # Page Object Model
│   ├── base_page.py       # resilient click, waits, evidence
│   ├── login_page.py
│   ├── pharmacy_selection_page.py
│   ├── my_products_page.py
│   ├── add_product_page.py
│   ├── product_catalog_page.py
│   ├── barcode_generator_page.py
│   ├── customization_list_page.py   # shared CRUD base
│   ├── company_page.py / generic_page.py / product_type_page.py
├── components/        # reusable UI widgets
│   ├── antd_select.py / data_table.py / pagination.py
│   ├── side_drawer.py / toast.py / confirm_modal.py / search_field.py
├── tests/
│   ├── conftest.py        # page-object fixtures wired to Manik Pharma
│   ├── products/
│   │   ├── test_login_and_pharmacy.py
│   │   ├── test_my_products.py
│   │   ├── test_add_product.py
│   │   ├── test_add_company_generic_from_drawer.py
│   │   ├── test_product_catalog.py
│   │   └── test_barcode_generator.py
│   ├── customization/
│   │   ├── test_company.py / test_generic.py / test_product_type.py
│   └── test_cross_module_integration.py
├── utils/             # data_generator, helpers, logger, constants
├── test_data/         # products.json, validation_data.json, bug_logs.json
├── tools/             # test_case_catalog.py, build_excel_report.py
├── screenshots/ · logs/ · reports/allure-results/
└── docs/QA_TASK_REPORT.md
```

---

## 3. Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
playwright install
```

---

## 4. Environment setup

Copy `.env.example` → `.env` and fill it in (`.env` is git-ignored):

```env
TEST_ENV=staging
STAGING_BASE_URL=https://pms-sql-portal.ems24.co/
LOGIN_PHONE=            # currently accepts an email address
LOGIN_PASSWORD=
PHARMACY_NAME=Manik Pharma
HEADLESS=true
RUN_DESTRUCTIVE_TESTS=false
```

`config/settings.py` reads `.env` **without** overriding real environment
variables, so `TEST_ENV=prod pytest` on the command line still wins.

Production is protected: destructive tests never run when `TEST_ENV=prod`,
regardless of `RUN_DESTRUCTIVE_TESTS`.

---

## 5. Running tests

```bash
pytest                                   # everything for the current TEST_ENV
pytest -m smoke                          # critical path only
pytest -m regression
pytest -m "regression and not destructive"
pytest -m "not blocked"                  # skip cases known-blocked in this env
pytest tests/products/test_product_catalog.py
TEST_ENV=local pytest                    # env switch (or: pytest --env local)
pytest --headed-run                      # force a visible browser
RUN_DESTRUCTIVE_TESTS=true pytest -m destructive   # create+delete QA data
```

### Markers

`smoke`, `regression`, `negative`, `boundary`, `integration`, `ui`,
`destructive`, `prod_safe`, `products`, `customization`, `blocked`.

> **`blocked`** — see §7. These tests are complete and correct; they are
> skipped only where the run environment cannot operate the app's custom
> AntD `<Select>` widgets. They pass on a normal desktop browser.

---

## 6. Allure reporting

```bash
pytest --alluredir=reports/allure-results
allure serve reports/allure-results
```

Every test carries `@allure.epic/feature/story/severity`; failures auto-attach
a full-page screenshot, the page URL/title, visible text and captured console
errors. `conftest.py` also writes `environment.properties`.

---

## 7. Interaction notes (read before extending page objects)

* **AntD `<Select>` is customised.** The chosen value renders in
  `div.ant-select-content` (`.ant-select-content-has-value`, plus a `title`
  attribute) — **not** the stock `.ant-select-selection-item`.
  `components/antd_select.py` reflects this: open `.ant-select-content` → focus
  `#<fieldId>` and type to filter the virtualised list → click
  `.ant-select-item-option`.
* **Clicks:** Playwright's synthetic `click()` sometimes doesn't fire this app's
  React handlers; a full JS pointer-event sequence does. `BasePage.click()`
  does native-first, then the JS-pointer fallback, and can verify the effect via
  an `expect_effect` predicate.
* **`@pytest.mark.blocked`** now marks tests whose *feature* is broken
  (BUG-PROD-002: the drawer `[+]` Add-Company/Generic buttons), not a tooling
  limit. `pytest -m "not blocked"` skips those.
* **Product / Product Type creation is broken in the app** (BUG-PROD-001 /
  BUG-PTYPE-001). The create tests assert the failure; seed data for this run was
  made with request-body workarounds (documented in `test_data/products.json`).

Full detail and the defect list are in `docs/QA_TASK_REPORT.md` §7–§8.

---

## 8. Test data

`utils/data_generator.py` produces unique, obvious QA values
(`QA_Auto_Product_<timestamp>_<rand>` etc.). Tests only mutate QA-tagged
records; deletes run only under the `destructive` marker with the safety flag on.
