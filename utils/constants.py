"""Static application knowledge captured during exploratory testing.

Routes, field metadata and validation copy live here so tests and page objects
share one source of truth.

Captured 2026-09-08; extended by the 2026-09-09 live re-run:
  * BUG-PROD-004  - Add Product has no client-side min/zero guard on the number
                    fields (retail = -5 and Qty/Box = 0 both reach the backend;
                    Qty/Box = 0 is accepted end to end).
  * BUG-PROD-005  - the Add / Edit Product drawer keeps its previous unsaved
                    input when reopened (no form reset).
  * BUG-PTYPE-002 - editing a Product Type name fails with the SAME raw
                    ``sortOrder ... expected a value of type int`` error as
                    create (BUG-PTYPE-001).
  * BUG-CO-001    - Add New Company has no client-side required validation
                    (Generic and Product Type add-forms do).
  * BUG-CAT-002   - Product Catalog header "Select all" selects the WHOLE
                    catalogue (41,005) in one click, no page-vs-all choice.
  * BUG-API-001   - intermittent API failures (missing CORS header / 500 / 404)
                    render as silent empty lists; no frontend error handling.
  * BUG-UX-001    - NOT reproduced 2026-09-09 (Esc did close the drawer).
  * Customization Edit control is an icon-only <div> (no accessible name) - see
                    CUSTOMIZATION_EDIT_ICON below.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Routes (SPA - client-side routed)
# ---------------------------------------------------------------------------
ROUTES = {
    "login": "login",
    "pharmacies": "pharmacies",
    "dashboard": "dashboard",
    "my_products": "my-products",
    "product_catalog": "product-catalog",
    "barcode_generator": "generate-barcode",
    # Customizations (confirmed live 2026-09-08)
    "company_list": "companies",
    "generic_list": "generics",
    "product_type_list": "product-types",
    "payment_method_list": "payment-methods",  # out of scope
    # Inventory (confirmed live 2026-09-14)
    "inventory": "inventory",
    "inventory_tp_vat": "inventory/tp-vat",
    "inventory_opening_stock": "inventory/opening-stock",
    "inventory_checkout": "inventory-checkout",
    "inventory_record": "inventory-record",
    "supplier_list": "supplier",
}

# ---------------------------------------------------------------------------
# Inventory module (functional spec: Knowledge/Inventory Management/Inventory
# Management.md). Field ids captured live 2026-09-14 from the "Add Items to
# Cart" panel - NOTE this panel is an inline side panel, NOT an
# ``.ant-drawer`` like Add New Product, so SideDrawer does not apply here.
# ---------------------------------------------------------------------------
INVENTORY_MODE_LABELS = ("Default", "TP/VAT", "Opening Stock")

INVENTORY_MODE_ROUTES = {
    "Default": ROUTES["inventory"],
    "TP/VAT": ROUTES["inventory_tp_vat"],
    "Opening Stock": ROUTES["inventory_opening_stock"],
}

# Fields common to all three modes.
INVENTORY_FIELDS_COMMON = {
    "company": "companyId",
    "product": "productId",
    "box_qty": "boxQty",
    "qty_per_box": "quantityInBox",
    "total_qty": "totalQty",
    "free_qty": "freeQty",
    "retail_price": "retailPricePerBox",
    "wholesale_price": "wholesalePricePerBox",
    "min_qty": "minQty",
    "rack_no": "rackNo",
    "storage_type": "storageType",
    "batch_no": "batchNo",
    "expiry_date": "expiryDate",
    "barcode_value": "barcodeValue",
    "special_discount": "specialDiscountValue",      # label "Special Discount (Tk)" - verified live 2026-10-11
}

# Per-mode purchase-price fields (everything else reuses INVENTORY_FIELDS_COMMON).
INVENTORY_FIELDS_BY_MODE = {
    "Default": {**INVENTORY_FIELDS_COMMON, "total_price": "totalItemPrice", "price_per_box": "btpVatPerBox"},
    "TP/VAT": {**INVENTORY_FIELDS_COMMON, "tp_per_box": "tpPerBox", "vat_per_box": "vatPerBox"},
    "Opening Stock": {**INVENTORY_FIELDS_COMMON, "total_price": "totalItemPrice",
                      "price_per_box": "btpVatPerBox", "opening_stock_percent": "openingStockPercent"},
}

INVENTORY_SYSTEM_VAT_PERCENT = 17.4          # spec section 11
INVENTORY_OPENING_STOCK_DEFAULT_PERCENT = 12  # spec section 15

# Checkout page (route: inventory-checkout) - stable field ids.
INVENTORY_CHECKOUT_FIELDS = {
    "supplier": "supplier",
    "discount_value": "discountValue",
    "paid_to_supplier": "paidToSupplier",
    "invoice_number": "invoiceNumber",
}

# ---------------------------------------------------------------------------
# Add New Product drawer - field ids (stable, taken from the live DOM)
# ---------------------------------------------------------------------------
ADD_PRODUCT_FIELDS = {
    "product_name": "productName",              # text, required, no maxlength
    "strength": "strength",                     # text, optional
    "product_type": "productType",              # AntD select, required
    "company": "company",                       # AntD select, required, has "+ add" button
    "generic": "generic",                       # AntD select, optional, has "+ add" button
    "qty_per_box": "quantityInBox",             # number, required, step=1, no min/max attr
    # DISABLED in the UI, NOT marked required, BUT the backend rejects create with
    # "Cost per box must not be null" -> product creation is blocked (BUG-PROD-001)
    "cost_per_box": "lastPurchasePricePerBox",
    "retail_price_per_box": "retailPricePerBox",   # number, required
    "wholesale_price_per_box": "wholesalePricePerBox",  # number, required
    "medicine": "medicine",                     # checkbox, default checked
    # --- Additional Information (collapsed by default) ---
    "rack_no": "rackNo",                        # number(!), step=1
    "barcode_value": "barcodeValue",            # text
    "volume": "volume",                         # text
    "origin": "origin",                         # AntD select (Country Of Origin)
}

# ``wholesale_price_per_box`` must be OPTIONAL per the product requirement; the build still enforces it on Add + Edit +
# backend (BUG-PROD-008).
WHOLESALE_REQUIRED_MESSAGE = "Wholesale price per box is required"
WHOLESALE_BACKEND_NULL_MESSAGE = "Wholesale price per box must not be null"

# Validation copy observed for empty submit (legit required fields only).
ADD_PRODUCT_REQUIRED_MESSAGES = {
    "product_name": "Product name is required",
    "product_type": "Product type is required",
    "company": "Company name is required",
    "qty_per_box": "Quantity per box is required",
    "retail_price_per_box": "Retail price per box is required",
}

# My Products list table columns (in order)
MY_PRODUCTS_COLUMNS = [
    "Name",
    "Stock Status",
    "Purchase Price",
    "Sale Price",
    "Location",
    "Actions",
]

# The per-row Edit control on the Customization lists is an icon-only clickable
# <div> (a pencil SVG) with NO text / aria-label / role="button" - only rows for
# records this pharmacy created (global:false) render it; tenant-wide (global)
# rows have an empty action cell.  Target it structurally, not by name.
CUSTOMIZATION_EDIT_ICON = "td:last-child div[style*='cursor']"

# Fragments that must NEVER appear in a user-facing message (toast or inline).
# The task brief explicitly calls out "expected a value of type int".
RAW_BACKEND_ERROR_FRAGMENTS = (
    "expected a value of type",
    "request body is missing",
    "traceback",
    "valueerror",
    "typeerror",
    "nonetype",
    "cannot convert",
    "slug must not be blank",
    "500 internal",
    "jsonmappingexception",
    "nested exception",
)

MY_PRODUCTS_SUMMARY_CARDS = [
    "Total SKUs",
    "Out of stock",
    "Low stock",
    "Expired",
    "Expiring ≤90d",
    "Stock value",
]

