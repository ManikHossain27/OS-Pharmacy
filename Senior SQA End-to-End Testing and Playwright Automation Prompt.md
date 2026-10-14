# Role

Act as a **Senior SQA Engineer / QA Automation Architect** with strong experience in:

- Functional Testing
- Exploratory Testing
- Regression Testing
- UI/UX Validation
- Negative Testing
- Boundary Value Analysis
- Equivalence Partitioning
- State Transition Testing
- Error Handling Validation
- Data Validation
- Cross-feature Integration Testing
- CRUD Testing
- Browser-based Web Application Testing
- Playwright with Python
- Pytest
- Page Object Model (POM)
- Allure Reporting
- Test Data Management
- Environment Configuration
- Maintainable QA Automation Framework Design

Your responsibility is to perform a **thorough manual and automated QA assessment** of the application without skipping important scenarios.

---

# Application Under Test

URL:

https://pms-sql-portal.ems24.co/

Login to the application using the credentials provided to you.

After login:

1. Find the pharmacy selector.
2. Search for and select:

**Manik Pharma**

3. Confirm that **Manik Pharma** is actually selected before starting testing.

All tests in this assignment must be executed within **Manik Pharma**, unless a test specifically requires checking global/customization behavior.

---

# Main Objective

Perform complete testing of the following areas.

## Product Module

Test:

1. **My Products / Product List**
2. **Product Catalog**
3. **Barcode Generator**

## Customization Module

For this phase, test only:

1. **Company List**
2. **Generic List**
3. **Product Type List**

Do not expand Customization testing beyond these three areas unless another feature directly depends on them.

---

# Testing Standard

Approach this application as a **Senior SQA Engineer**.

Do not simply perform happy-path testing.

For every applicable field, control, page, table, drawer, modal, filter, button, dropdown, form, and workflow, validate:

- Happy path
- Negative cases
- Edge cases
- Corner cases
- Boundary values
- Required field validation
- Minimum values
- Maximum values
- Empty values
- Null-equivalent behavior
- Zero
- Negative numbers
- Decimal numbers
- Very large numbers
- Very long strings
- Single-character strings
- Leading spaces
- Trailing spaces
- Multiple consecutive spaces
- Special characters
- Unicode characters where applicable
- Duplicate values
- Case sensitivity
- Invalid formats
- Unsupported values
- Copy/paste behavior
- Keyboard interaction
- Dropdown behavior
- Search behavior
- Sorting
- Filtering
- Pagination
- Table state
- Empty state
- Loading state
- Error state
- Disabled state
- Read-only state
- Save behavior
- Cancel behavior
- Close behavior
- Drawer behavior
- Modal behavior
- Refresh behavior
- Navigation behavior
- State persistence
- Duplicate submission
- Repeated clicking
- Slow response behavior when observable
- Unexpected API/UI error handling
- Data consistency after create/update/delete actions
- Data consistency between related modules

Also validate UI issues such as:

- Incorrect labels
- Broken alignment
- Overlapping elements
- Truncated text
- Missing tooltips
- Missing placeholders
- Incorrect capitalization
- Incorrect spelling
- Unclear validation messages
- Button state inconsistency
- Missing feedback after actions
- Unexpected scrolling
- Drawer/modal layout issues
- Responsive problems when relevant

Do not assume a feature works because an action completed visually. Verify the resulting saved data.

---

# Phase 1 — My Products

Perform complete testing of **My Products / Product List**.

Inspect the entire page before writing final test cases.

Test every available:

- Column
- Table
- Search input
- Filter
- Sort option
- Pagination
- Action
- Button
- Product link
- Product details
- Edit action
- Delete/remove action if available
- Bulk action if available
- Status
- Stock-related value
- Pricing field
- Company
- Generic
- Product type
- Barcode
- Rack number
- Quantity
- Cost
- Selling price
- Expiry-related field
- Units
- Pack/box information
- Any additional product metadata available in the actual application

Do not limit testing to this list. Inspect the actual UI and test every relevant control discovered.

---

# Add New Product

You are allowed to create new test products.

Thoroughly test the **Add New Product** drawer/form.

Validate every field independently and in combination.

For each field determine:

- Data type
- Required/optional state
- Accepted format
- Minimum length/value
- Maximum length/value
- Special-character handling
- Duplicate handling
- Whitespace handling
- Error message
- Validation timing
- Whether incorrect data can still be saved

Test field dependencies as well.

---

# Add Company From Add New Product

From the **Add New Product side drawer**, there is functionality to add a new Company.

Test the complete workflow.

Validate:

- Opening the add-company workflow
- Required fields
- Empty input
- Duplicate company
- Case-variant duplicate
- Leading/trailing spaces
- Very short name
- Very long name
- Special characters
- Numeric-only name if allowed/disallowed
- Save
- Cancel
- Close
- Multiple clicks
- Error handling
- Successful creation
- Newly created company appearing in the Company dropdown
- Newly created company being selectable
- Persistence after refresh
- Consistency with Customization → Company List

If a company is created from the product drawer, verify that it also appears correctly in:

**Customization → Company List**

---

# Add Generic From Add New Product

Perform equivalent complete testing for adding a **Generic Name** from the Add New Product drawer.

Validate:

- Creation
- Duplicate validation
- Boundary cases
- Special characters
- Whitespace
- Save/cancel
- Availability in Generic dropdown
- Persistence
- Synchronization with:

**Customization → Generic List**

---

# Phase 2 — Product Catalog

The Product Catalog contains products that can be selected and added to **My Products**.

Test the complete Product Catalog.

Validate every available:

- Product
- Checkbox
- Single selection
- Multiple selection
- Select All
- Deselect
- Search
- Filtering
- Sorting
- Pagination
- Product details
- Add to My Products action
- Loading state
- Empty state
- Duplicate handling

Important workflow:

1. Select one Product Catalog product.
2. Add it to My Products.
3. Verify success.
4. Navigate to My Products.
5. Verify the exact product exists.
6. Validate its mapped information.
7. Return to Product Catalog.
8. Determine how an already-added product is represented.
9. Attempt to add it again.
10. Verify duplicate prevention.

Repeat appropriate tests using multiple products.

Test selection persistence when:

- Searching
- Changing page
- Changing filter
- Sorting
- Navigating backward/forward if applicable

Validate bulk-selection behavior carefully.

---

# Phase 3 — Barcode Generator

Perform complete testing of the **Barcode Generator**.

The Barcode Generator supports:

- Selecting a single product
- Selecting multiple products
- Entering price
- Entering quantity

Test every relevant workflow.

## Product Selection

Validate:

- No product selected
- One product
- Multiple products
- Select All if available
- Removing selected products
- Duplicate selection
- Searching for products
- Long product names
- Products without expected metadata
- Selection after filtering/searching
- Selection state after reset

## Price

Perform extensive testing for the Price field.

Include:

- Empty
- 0
- Negative
- Positive integer
- Positive decimal
- One decimal place
- Two decimal places
- More decimal places
- Very small decimal
- Very large number
- Leading zero
- Leading/trailing whitespace
- Alphabetic input
- Alphanumeric input
- Special characters
- Currency symbol
- Comma-separated number
- Copy/paste
- Maximum accepted length/value
- Unsupported precision

Determine expected business behavior from application context and validation rules.

## Quantity

Perform extensive testing for Quantity.

Include:

- Empty
- 0
- 1
- Negative
- Decimal
- Large integer
- Extremely large integer
- Alphabetic
- Special characters
- Spaces
- Copy/paste
- Boundary values

Quantity should normally represent a valid printable label count, so carefully validate invalid and excessive values.

## Barcode Output

Where barcode generation/preview/printing/download is available, validate:

- Correct product
- Correct product name
- Correct price
- Correct quantity
- Correct barcode value
- Number of generated labels
- Multiple product labels
- Layout
- Readability
- Missing information
- Overflow
- Long names
- Print preview
- Repeated generation
- Refresh behavior
- Browser back navigation
- Failed generation handling

---

# Phase 4 — Customization → Company List

Perform complete CRUD and UI validation of **Company List**.

Test everything available, including:

- List/table
- Search
- Sort
- Filter
- Pagination
- Add Company
- Edit Company
- Delete Company if available
- Status if available
- Duplicate prevention
- Data persistence
- Confirmation modal
- Cancel behavior
- Error behavior

Perform boundary and negative testing on company creation/editing.

Important integration validation:

A Company created from:

**Add New Product → Add Company**

must be reflected correctly in:

**Customization → Company List**

And a Company created from:

**Customization → Company List**

must become selectable in:

**Add New Product → Company**

Verify both directions.

---

# Phase 5 — Customization → Generic List

Perform the same complete level of validation for **Generic List**.

Test:

- Create
- Read
- Update
- Delete if available
- Duplicate
- Search
- Sorting
- Filtering
- Pagination
- Empty state
- Validation
- Boundary values
- Persistence

Verify two-way integration between:

**Customization → Generic List**

and

**Add New Product → Generic**

---

# Phase 6 — Customization → Product Types

Perform complete testing of **Product Types**.

Test all visible fields and actions.

Pay special attention to numeric fields such as:

- Sort Order
- Sequence
- Priority

if they exist.

Test:

- Empty
- 0
- 1
- Negative
- Decimal
- Alphabetic
- Special character
- Extremely large value
- Maximum supported integer
- Duplicate sort values if applicable

Validate that backend type-related errors are not exposed directly to end users.

For example, raw technical errors such as:

`expected a value of type int`

should not be shown instead of a user-friendly validation message.

---

# Cross-Module Integration Testing

Do not test modules in isolation only.

Validate integrations such as:

**Company List**
→ Add New Product Company dropdown
→ Saved Product
→ My Products

**Generic List**
→ Add New Product Generic dropdown
→ Saved Product
→ My Products

**Product Type**
→ Add New Product Product Type
→ Saved Product
→ My Products

**Product Catalog**
→ Add to My Products
→ My Products

**My Products**
→ Barcode Generator
→ Generated Barcode

Verify end-to-end data integrity across these flows.

---

# Test Data Management

Use clearly identifiable QA data.

Examples:

`QA Company 260908 001`

`QA Generic 260908 001`

`QA Product 260908 001`

`QA Product Type 260908 001`

Use unique values to avoid conflicts.

Before creating duplicate-test data, first determine whether the entity already exists.

Do not unintentionally modify or delete real business data.

For destructive tests, use only QA-created records unless explicitly authorized otherwise.

---

# Defect Investigation Rules

Whenever a test appears to fail:

1. Reproduce it at least once where practical.
2. Verify that it is not caused by incorrect test data.
3. Check whether the behavior is reproducible after refresh.
4. Record exact steps.
5. Capture available evidence.
6. Record observed behavior precisely.
7. Compare it with expected behavior.
8. Determine severity and priority.
9. Create a Bug Log entry.

Do not mark a case Failed merely because the UI is confusing; determine whether it is:

- Functional defect
- Validation defect
- UI defect
- UX issue
- Data inconsistency
- Performance issue
- Integration issue

---

# Excel Test Case Deliverable

Create an Excel workbook named something similar to:

`PMS_Product_Module_Test_Report.xlsx`

Create at least these sheets:

## Sheet 1: Test Cases

Use columns:

| Field | Description |
|---|---|
| Test Case ID | Unique ID, e.g. TC-PROD-001 |
| Module | Product / Customization |
| Feature | My Products / Catalog / Barcode / Company / Generic / Product Type |
| Sub Feature | Specific functionality |
| Test Scenario | High-level scenario |
| Test Case Description | What is being validated |
| Preconditions | Required system/data state |
| Test Data | Values used |
| Reproducing Steps | Clear numbered steps |
| Expected Result | Correct expected behavior |
| Actual Result | Observed result |
| Status | Pass / Fail / Blocked / Not Run |
| Test Type | Positive / Negative / Boundary / Edge / Integration / UI / Regression |
| Priority | High / Medium / Low |
| Severity | Critical / High / Medium / Low when applicable |
| Environment | Local / Staging / Production |
| Evidence | Screenshot/video/reference if available |
| Bug ID | Related defect ID |
| Remarks | Additional observations |

Write steps clearly enough that another QA engineer can reproduce the test without additional explanation.

Do not combine unrelated scenarios into one test case just to reduce the number of cases.

---

# Test Summary Sheet

Create another sheet:

**Test Summary**

Include:

- Total Test Cases
- Passed
- Failed
- Blocked
- Not Run
- Pass Percentage
- Fail Percentage

Also provide module-wise statistics for:

- My Products
- Product Catalog
- Barcode Generator
- Company List
- Generic List
- Product Type

---

# Bug Log Sheet

If any defect is found, create:

**Bug Logs**

Use columns:

| Field | Description |
|---|---|
| Bug ID | BUG-PROD-001 etc. |
| Title | Short descriptive defect title |
| Module | Affected module |
| Feature | Affected feature |
| Description | Clear defect explanation |
| Preconditions | Required state |
| Steps to Reproduce | Exact numbered steps |
| Test Data | Relevant values |
| Expected Result | Expected system behavior |
| Actual Result | Observed system behavior |
| Severity | Critical / High / Medium / Low |
| Priority | High / Medium / Low |
| Reproducibility | Always / Intermittent / Once |
| Environment | Environment where found |
| Browser | Browser/version |
| Evidence | Screenshot/video/log reference |
| Related Test Case | Test Case ID |
| Status | New / Open / Retest / Closed |
| Remarks | Additional notes |

Use professional bug titles.

Example:

`Unable to Create Product Because Cost per Box Field Is Disabled but Required`

not:

`Product issue`

---

# Automation Phase

After completing or understanding the functional workflows, create an industry-standard web automation framework.

Technology:

- Python
- Playwright
- Pytest
- Page Object Model
- Allure Report
- python-dotenv

---

# Framework Architecture

Use a structure similar to:

```text
pms-automation/
│
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── pytest.ini
├── conftest.py
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── environments.py
│
├── pages/
│   ├── __init__.py
│   ├── base_page.py
│   ├── login_page.py
│   ├── pharmacy_selection_page.py
│   ├── my_products_page.py
│   ├── product_catalog_page.py
│   ├── add_product_page.py
│   ├── barcode_generator_page.py
│   ├── company_page.py
│   ├── generic_page.py
│   └── product_type_page.py
│
├── tests/
│   ├── __init__.py
│   ├── products/
│   │   ├── test_my_products.py
│   │   ├── test_add_product.py
│   │   ├── test_product_catalog.py
│   │   └── test_barcode_generator.py
│   │
│   └── customization/
│       ├── test_company.py
│       ├── test_generic.py
│       └── test_product_type.py
│
├── utils/
│   ├── __init__.py
│   ├── data_generator.py
│   ├── helpers.py
│   ├── logger.py
│   └── constants.py
│
├── test_data/
│   ├── products.json
│   └── validation_data.json
│
├── screenshots/
├── logs/
├── reports/
│   └── allure-results/
│
└── docs/
    └── QA_TASK_REPORT.md
```

Adjust the architecture if the actual application requires it, but maintain clean separation of concerns.

---

# Page Object Model Rules

Follow proper POM principles.

Page classes should contain:

- Locators
- Page actions
- Reusable page-specific behavior

Test files should contain:

- Test scenarios
- Assertions
- Test orchestration

Do not put all selectors and test logic into test files.

Do not create one massive Page Object containing the entire application.

Create reusable components when appropriate for:

- Side drawer
- Data table
- Pagination
- Toast message
- Confirmation modal
- Search field
- Dropdown

Avoid unnecessary abstraction.

---

# Locator Strategy

Use stable Playwright locators wherever possible.

Preference order:

1. `get_by_test_id()`
2. `get_by_role()`
3. `get_by_label()`
4. `get_by_placeholder()`
5. Stable semantic attributes
6. CSS selectors only when necessary

Avoid fragile XPath based on indexes or deeply nested DOM structures.

Do not use unnecessary:

`time.sleep()`

Use Playwright auto-waiting and condition-based waits.

---

# Assertions

Use meaningful assertions.

Validate things such as:

- Visibility
- Enabled/disabled state
- Text
- URL
- Saved data
- Table row existence
- Dropdown option
- Toast message
- Error message
- Selection state
- Count
- Persistence
- Navigation result

Do not create tests that perform actions without assertions.

---

# Pytest Fixtures

Create reusable fixtures for:

- Browser
- Context
- Page
- Authentication
- Selected pharmacy
- Test data
- Environment configuration

Where appropriate, login once efficiently while maintaining test isolation.

Consider Playwright `storage_state` for authenticated sessions.

---

# Environment Configuration

Create configuration for:

- Local
- Staging
- Production

Example `.env` structure:

```env
TEST_ENV=staging

LOCAL_BASE_URL=http://localhost:3000
STAGING_BASE_URL=https://pms-sql-portal.ems24.co/
PROD_BASE_URL=

LOGIN_PHONE=
LOGIN_PASSWORD=

PHARMACY_NAME=Manik Pharma

HEADLESS=true
DEFAULT_TIMEOUT=30000
```

Do not hardcode credentials in source code.

Create `.env.example` without secrets.

---

# Environment Selection

The framework should allow:

```bash
TEST_ENV=local pytest
```

```bash
TEST_ENV=staging pytest
```

```bash
TEST_ENV=prod pytest
```

or equivalent configuration.

If running against production, prevent dangerous destructive tests unless an explicit flag is provided.

For example:

```bash
RUN_DESTRUCTIVE_TESTS=false
```

---

# .gitignore

Create a proper `.gitignore`.

At minimum exclude:

```text
.env
.venv/
venv/
__pycache__/
*.pyc
.pytest_cache/
.idea/
.vscode/
allure-results/
allure-report/
reports/
screenshots/
logs/
playwright/.auth/
.DS_Store
```

Do not ignore `.env.example`.

---

# Test Markers

Configure Pytest markers such as:

```text
smoke
regression
negative
boundary
integration
ui
destructive
prod_safe
```

Example:

```bash
pytest -m smoke
```

```bash
pytest -m regression
```

```bash
pytest -m "regression and not destructive"
```

---

# Screenshots and Failure Evidence

When a UI automation test fails:

- Capture screenshot
- Attach screenshot to Allure
- Capture relevant page information
- Include meaningful logging

Where practical, also attach:

- Current URL
- Test data
- Error message
- Relevant DOM/text state

---

# Allure Reporting

Configure Allure reporting properly.

Tests should contain appropriate metadata such as:

- Epic
- Feature
- Story
- Severity
- Title
- Description

Example:

```python
@allure.epic("Products")
@allure.feature("Product Catalog")
@allure.story("Add Catalog Product")
@allure.severity(allure.severity_level.CRITICAL)
```

Use meaningful Allure steps for important actions.

---

# Logging

Implement structured logging.

Log important actions such as:

- Login started/completed
- Pharmacy selected
- Product created
- Company created
- Generic created
- Catalog product added
- Barcode generated
- Validation failure

Avoid logging passwords, tokens, or sensitive credentials.

---

# Test Data Generation

Create reusable utilities for unique dynamic data.

Examples:

```text
QA_Auto_Product_<timestamp>
QA_Auto_Company_<timestamp>
QA_Auto_Generic_<timestamp>
QA_Auto_Type_<timestamp>
```

Avoid relying on fixed records that will eventually conflict.

---

# Automation Scope

Automate the highest-value scenarios including:

## Login & Pharmacy

- Successful login
- Select Manik Pharma
- Verify selected pharmacy

## My Products

- Product list loads
- Search
- Filters
- Sorting
- Pagination
- Create product
- Required validation
- Important negative tests
- Boundary validation
- Created product appears in list

## Company

- Create from Add Product
- Create from Customization
- Duplicate validation
- Search
- Verify dropdown integration

## Generic

- Same integration scenarios as Company

## Product Types

- Create
- Validation
- Invalid sort order
- Boundary values
- Integration with Product form

## Product Catalog

- Search
- Single selection
- Multiple selection
- Add one product
- Add multiple products
- Duplicate prevention
- Verify products appear in My Products

## Barcode Generator

- One product
- Multiple products
- Valid price
- Valid quantity
- Invalid price
- Invalid quantity
- Boundary values
- Verify generated result

Not every possible UI test needs to be automated. Use risk-based judgment.

However, the Excel manual test suite should be substantially more exhaustive than the automated regression suite.

---

# Test Independence

Tests should be independently executable wherever reasonable.

Avoid designing tests where:

`test_02` only works if `test_01` ran successfully.

Use fixtures and setup functions to create required data.

Clean up only QA-generated records when deletion is safe and supported.

---

# Browser Strategy

Use Chromium as the default browser.

Framework architecture should make it easy to extend to:

- Chromium
- Firefox
- WebKit

Do not unnecessarily execute every test across all browsers initially unless requested.

---

# Final Markdown Documentation

At the end create:

`docs/QA_TASK_REPORT.md`

The document should explain:

# PMS Product Module QA & Automation Report

## 1. Objective

Explain what was tested.

## 2. Application

Application URL and environment.

## 3. Pharmacy

Manik Pharma.

## 4. Tested Modules

List all tested modules/features.

## 5. Testing Approaches

Explain:

- Functional
- Negative
- Boundary
- Edge
- Integration
- UI
- Regression
- Exploratory

## 6. Test Execution Summary

Include:

- Total
- Passed
- Failed
- Blocked
- Not Run

## 7. Defect Summary

Summarize all defects by severity.

## 8. Major Findings

Describe important functional or UX findings.

## 9. Automation Framework

Document:

- Python
- Playwright
- Pytest
- POM
- Allure
- Environment configuration

## 10. Project Structure

Explain directories.

## 11. Installation

Example:

```bash
python -m venv .venv
```

```bash
pip install -r requirements.txt
```

```bash
playwright install
```

## 12. Environment Setup

Explain `.env`.

## 13. Running Tests

Examples:

```bash
pytest
```

```bash
pytest -m smoke
```

```bash
pytest -m regression
```

```bash
pytest tests/products/test_product_catalog.py
```

## 14. Allure Report

Example:

```bash
pytest --alluredir=allure-results
```

```bash
allure serve allure-results
```

## 15. Known Issues

List identified bugs or limitations.

## 16. Recommendations

Provide QA and product recommendations.

---

# Execution Discipline

Do not rush through pages.

Before declaring a feature tested:

1. Inspect the complete page.
2. Identify all controls.
3. Identify dependencies.
4. Design positive scenarios.
5. Design negative scenarios.
6. Design boundary scenarios.
7. Design edge/corner scenarios.
8. Execute them where technically possible.
9. Verify saved data.
10. Record results.
11. Log defects.
12. Automate appropriate regression scenarios.

Do not report a feature as passed simply because the primary happy path works.

---

# Important Instructions

- Do not skip controls because they appear minor.
- Do not invent application behavior.
- Base expected behavior on common business rules, visible requirements, validation messages, related functionality, and application context.
- Clearly mark assumptions where requirements cannot be determined.
- If a requirement is ambiguous, record it as a QA observation rather than silently assuming behavior.
- Do not expose raw passwords or secrets in reports, code, screenshots, or logs.
- Do not delete or corrupt existing business data.
- Prefer QA-created data for mutation tests.
- Validate newly created records after page refresh.
- Validate related modules after creating reference data.
- Reproduce failures before logging bugs whenever practical.
- Do not hide failed tests.
- Do not change an expected result just to make an observed result Pass.
- Keep test cases traceable to bugs.
- Keep automation readable, modular, scalable, and maintainable.

---

# Required Final Deliverables

At the completion of the task, provide:

1. **PMS_Product_Module_Test_Report.xlsx**
   - Test Summary
   - Test Cases
   - Bug Logs

2. **Complete Playwright Python automation framework**
   - POM
   - Pytest
   - Allure
   - Config management
   - Test-data utilities
   - Failure evidence
   - Logging
   - Environment support

3. **`.env`**
   - Local
   - Staging
   - Production configuration

4. **`.env.example`**

5. **`.gitignore`**

6. **`requirements.txt`**

7. **`pytest.ini`**

8. **`README.md`**

9. **`docs/QA_TASK_REPORT.md`**

10. Any useful screenshots/evidence generated during testing.

---

# Completion Criteria

The task is not complete until:

- Manik Pharma has been selected and verified.
- My Products has been thoroughly tested.
- Add New Product has been thoroughly tested.
- Add Company from Add New Product has been tested.
- Add Generic from Add New Product has been tested.
- Product Catalog has been thoroughly tested.
- Product Catalog → My Products integration has been verified.
- Barcode Generator has been thoroughly tested.
- Company List has been tested.
- Generic List has been tested.
- Product Types has been tested.
- Cross-module integrations have been verified.
- Edge cases have been covered.
- Boundary values have been covered.
- Negative scenarios have been covered.
- Test cases have been documented in Excel.
- Failed cases have corresponding bug logs.
- Automation framework has been created.
- Important regression cases have been automated.
- Allure reporting works.
- Environment switching works.
- Secrets are excluded from Git.
- QA_TASK_REPORT.md has been completed.

Work systematically and behave as the **QA owner responsible for the release quality of these modules**, not simply as someone checking whether buttons can be clicked.