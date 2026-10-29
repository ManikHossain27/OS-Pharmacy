# Use this document only for Sale Management System (POS, Sales Lifecycle, & Customer Management System) functional and operational requirements. For other modules, refer to their respective documentation.

---

## 1. Executive Summary & Purpose

This document specifies the functional and operational requirements for the **Point of Sale (POS), Sales Lifecycle, and Customer Management System**. Designed for pharmacy, retail, and wholesale environments, it covers end-to-end sales operations: dynamic sales configurations, loyalty programs, customer ledgers, checkout workflows, FEFO-based inventory deduction, cashier approvals, post-sale audit trails, and item-level proportional sales returns.

---

## 2. System Settings & Configuration Rules

### 2.1 Sale Settings (`Settings > Sale Config`)
The system adapts its user interface and operational rules based on toggles configured under `Sale Config`:

1. **Out of Stock Sale**
   - **Enabled (ON)**: Products with zero (`0`) or negative stock quantity appear in product search menus and can be added to cart and sold (stock balance goes into negative numbers).
   - **Disabled (OFF)**: Any product with zero or negative inventory is hidden from sales dropdowns and search auto-completes.

2. **Allow Loss Sale**
   - **Disabled (OFF)**: The system blocks transactions and shows a warning prompt if the selling price is less than the purchase cost.
   - **Enabled (ON)**: Sellers are permitted to sell products below cost without restriction.

3. **Stock Quantity Display**
   - **Enabled (ON)**: Live available stock figures are visible in search dropdowns and cart line items.
   - **Disabled (OFF)**: Stock quantities are hidden across all POS search and cart views.

4. **Company / Brand Name**
   - **Enabled (ON)**: Shows the pharmaceutical company / manufacturer / brand name in search dropdowns and cart line items.
   - **Disabled (OFF)**: Hides manufacturer/brand names from the interface.

5. **Profit Margin Display**
   - **Enabled (ON)**: Estimated gross profit and profit margins are visible on the checkout screen.
   - **Disabled (OFF)**: Hides all profit metrics from cashier and sales views.

6. **Rack / Shelf Number**
   - **Enabled (ON)**: Displays physical shelf/rack location in search menus and cart line items to help staff locate items quickly.
   - **Disabled (OFF)**: Hides rack locations from the interface.

7. **Separate Cashier Workflow**
   - **Enabled (ON)**: Sales submitted at the sales counter enter a `Pending Cashier Approval` queue. A designated cashier must review, adjust if necessary, and complete the transaction. Financial ledgers and inventory deductions do not take effect until cashier approval is granted.
   - **Disabled (OFF)**: Sales finalize immediately upon checkout completion, updating inventory and accounting ledgers instantly.

---

### 2.2 Customer Loyalty Settings (`Settings > Loyalty Program Config`)

- **Earning Rule**: Defined as `Every X Tk purchase = 1 point`.
- **Redemption Rule**: Defined as `Y points = 1 Tk discount`.
- **Minimum Redemption Threshold**: Minimum point balance a customer must accumulate before they can redeem points.
- **Maximum Redemption Limit**: Upper cap on points redeemable on a single invoice.
- **OTP Verification**: Redeeming points requires SMS OTP verification sent to the customer's registered phone number (3-minute expiry).

---

## 3. Customer Classification & Management

### 3.1 Customer Types at POS
1. **Walk-in Customer (Guest)**
   - Used for quick or anonymous buyers.
   - Name and phone number fields are optional.
   - Ineligible for loyalty points and cannot carry customer account balances (Due or Advance).
   - Any payment underpayment or overpayment is resolved as **Less & Sale** or **Profit & Sale**.

2. **Registered Customer**
   - Searchable by Name or Phone Number.
   - Selecting a profile immediately displays live financial metadata:
     - **Previous Balance**: Formatted clearly as `Adv. (Tk)` or `Due (Tk)`.
     - **Loyalty Points**: Current available balance.
     - **Projected New Balance**: Real-time preview of the updated balance once the current transaction settles.
   - **Default Customer Discount**: Pre-configured profile discount percentage automatically applies to the checkout discount field.

### 3.2 Customer Management Module
- **Customer List**: Tabular view displaying `Name`, `Phone`, `Loyalty Points`, `Total Orders`, `Total Spent`, `Balance Status`, and `Account Status`.
- **Profile Fields**: Name (Mandatory), Phone (Mandatory & Unique), Address (Optional), Opening Balance (Due/Advance - Optional), Default Discount % (Optional), and Due Payment Term / Credit Due Date.
- **Account Actions**:
  - **Add Payment**: Collect pending dues or record advance deposits.
  - **Customer Ledger**: Detailed chronological record of all invoices, collections, returns, and adjustments.
  - **Payment History**: Breakdown of payments by tender types.
  - **Bad Debt Write-off**: Settle uncollectible receivables with mandatory supervisor reason notes.
- **Loyalty Member Activation**: Requires SMS OTP verification to confirm mobile number ownership before point accrual begins.

---

## 4. POS Terminal & Checkout Workflow

### 4.1 Mode of Sale
The terminal supports two distinct operational modes:
- **Retail Mode**: Default unit is Pieces (Pcs), using retail price schedules.
- **Wholesale Mode**: Default unit is Box, using wholesale tier pricing.

### 4.2 Product Search & Cart Operations
1. **Search & Auto-Complete**:
   - Filtered by the `Out of Stock Sale` setting.
   - Displays Name, Strength, Company Name (if configured), Rack Number (if configured), and Available Stock (if configured).
2. **Packaging Unit Conversion**:
   - Easily toggle between `Pcs` and `Box`.
   - Unit price auto-fills from the latest inventory pricing schedule:
     $$\text{Price per Box} = \text{Price per Pcs} \times \text{Pcs per Box}$$
3. **Item-Level Discounts**:
   - Sellers can apply individual line discounts as a flat amount (Tk) or percentage (%).
   - Line Total $= (\text{Quantity} \times \text{Unit Price}) - \text{Line Discount}$.
4. **Hold Sale**:
   - Active carts can be placed on hold with an optional reference note and timestamp, allowing other transactions to be processed before resuming.

---

### 4.3 Checkout Screen & Payment Calculation

- **Summary Totals**: Total Item Count, Total Gross Amount, Cumulative Line Discounts.
- **Overall Order Discount**:
  - Can be set as flat (Tk) or percentage (%).
  - **Exclusion Rule**: Any item that already received an individual line discount is excluded from the overall order discount base calculation.
- **Loyalty Point Discount**: Value of redeemed points deducted after OTP verification.
- **Round-Off Amount**: Fractional adjustments ensuring the final payable amount is strictly a whole number (integer).
- **Final Payable Amount**:
  $$\text{Final Price} = \text{Gross Total} - \text{Line Discounts} - \text{Overall Discount} - \text{Loyalty Discount} \pm \text{Round Off}$$
- **Split Payments**: Customer payment can be split across multiple methods: Cash, Bank Card, Bank Transfer, or MFS (bKash, Nagad, etc.).
- **Quick Print**: If checked, automatically sends the invoice to the receipt printer upon completion. If unchecked, completes the order without opening the print dialog.

---

### 4.4 Transaction Settlement Matrix

The system determines the transaction status based on customer type and the difference between amount paid and final payable price:

| Condition | Customer Type | Settlement Classification | Ledger & Profit Behavior |
| :--- | :--- | :--- | :--- |
| **Paid == Final Price** | Any | **Completed Sale** | Transaction settles in full. Customer balance unchanged. |
| **Paid < Final Price** | Registered | **Due & Sale** | Unpaid balance is added to the customer's credit ledger. |
| **Paid < Final Price** | Walk-in (Guest) | **Less & Sale** | Deficit is distributed across sold items, reducing order net profit. |
| **Paid > Final Price** | Registered | **Advance & Sale** | Overpaid surplus is credited to the customer's account for future purchases. |
| **Paid > Final Price** | Walk-in (Guest) | **Profit & Sale** | Overpaid surplus is distributed across sold items, increasing order net profit. |

---

## 5. Inventory Deduction & Profit Calculation Rules

### 5.1 FEFO (First Expired, First Out) Inventory Depletion
- Products are deducted from the active batch with the nearest expiration date.
- **Multi-Batch Deduction**: If the required quantity exceeds Batch 1 stock, the remaining quantity is fulfilled from Batch 2 (and subsequent batches in chronological expiry order). Each batch's purchase cost is tracked independently.

### 5.2 Cost of Goods Sold (COGS) & Fallback Logic
- The unit purchase cost is obtained directly from the depleted batch.
- **Fallback Rule**: If inventory is sold with no existing batch records or into negative stock:
  $$\text{Purchase Cost per Pcs} = \frac{\text{Last Purchase Price per Box}}{\text{Pcs per Box}}$$

### 5.3 Proportional Profit Allocation
1. **Base Profit**:
   $$\text{Line Base Profit} = (\text{Selling Price} \times \text{Sold Quantity}) - \text{Total Batch Purchase Costs}$$
2. **Order-Level Adjustments Distribution**:
   - Global adjustments (Overall Discounts, Loyalty Discounts, Less & Sale deficit, Profit & Sale surplus, Round-off) are allocated across products proportionally based on their share of eligible order gross revenue:
     $$\text{Item Weight} = \frac{\text{Line Subtotal}}{\text{Sum of Eligible Line Subtotals}}$$
     $$\text{Line Net Profit} = \text{Line Base Profit} - (\text{Total Order Adjustments} \times \text{Item Weight})$$

---

## 6. Cashier Approval Workflow (When Enabled)

1. The salesperson builds the cart and submits the order.
2. The transaction is marked as `Pending Cashier Approval`. Stock is reserved, but accounting ledgers and permanent inventory logs are not committed.
3. The cashier opens the approval queue, reviews items, modifies quantities, discounts, or payment tenders if needed, and clicks **Approve & Complete**.
4. Financial vouchers post permanently, stock is officially deducted, and the final receipt is generated.

---

## 7. Post-Sale Operations & Sales Returns

### 7.1 Sale Records & History
- Comprehensive grid with filters by date, invoice number, customer, and cashier.
- **View Details**: Full breakdown of batches, costs, discounts, and cashier approvals.
- **Edit Sale**: Modify a finalized sale. Any change creates an immutable entry in the **Sale Edit History** detailing user ID, timestamp, and before/after values.
- **Pay Due**: Direct modal to collect dues against credit sales and print payment vouchers.
- **Cancel Sale**: Reverses all batch stock deductions and credit/debit ledger entries.

---

### 7.2 Proportional Sale Return Calculation (Item-by-Item)

When an invoice contains multiple items with order-level discounts or surcharges, and a customer returns only a specific item or partial quantity, the refund value must reflect that item's **net realized price**:

#### Calculation Steps:
1. **Line Subtotal**:
   $$\text{Line Subtotal} = (\text{Unit Selling Price} \times \text{Sold Quantity}) - \text{Line Item Discount}$$
2. **Net Order-Level Adjustments**:
   $$\text{Net Adjustments} = \text{Overall Discount} + \text{Loyalty Discount} + \text{Less Deficit} - \text{Profit Surplus} \pm \text{Round Off}$$
3. **Item Proportion (Weight)**:
   $$\text{Item Weight} = \frac{\text{Line Subtotal}}{\text{Sum of Eligible Line Subtotals}}$$
4. **Allocated Adjustment**:
   $$\text{Allocated Adjustment} = \text{Net Adjustments} \times \text{Item Weight}$$
5. **Net Realized Unit Price**:
   $$\text{Net Realized Unit Price} = \frac{\text{Line Subtotal} - \text{Allocated Adjustment}}{\text{Original Sold Quantity}}$$
6. **Total Refund Amount**:
   $$\text{Refund Amount} = \text{Net Realized Unit Price} \times \text{Returned Quantity}$$

#### Concrete Example:
- **Original Invoice**:
  - Item A: 2 pcs @ 100 Tk = 200 Tk (No line discount)
  - Item B: 1 pc @ 300 Tk = 300 Tk (No line discount)
  - Gross Total = 500 Tk
  - Overall Checkout Discount = 50 Tk (Proportion: 40% to Item A, 60% to Item B)
  - Customer Paid = 450 Tk
- **Line Net Realization**:
  - Item A Net Total $= 200\text{ Tk} - (50\text{ Tk} \times 0.40) = 180\text{ Tk}$
  - Item A Effective Unit Refund Price $= \frac{180\text{ Tk}}{2} = 90\text{ Tk per pc}$
- **Return Action**:
  - If the customer returns **1 pc of Item A**, the refund is exactly **90 Tk** (not the list price of 100 Tk).
- **Inventory & Accounting Impact**:
  - Returned units are restored to their original batches.
  - Realized gross profit recognized for returned units is deducted from profit reports.
  - Refund is settled via Cash, reduction of Customer Due balance, or credit to Customer Advance balance.

---

## 8. Non-Functional & Security Requirements

- **Precision & Rounding**: Monetary amounts maintain 2 decimal places internally; checkout final payable amounts round to whole integers.
- **Concurrency Control**: Strict database row-locking on batch inventory during checkout to prevent duplicate sales of the same batch in high-volume stores.
- **Audit Trails**: Security logs with staff ID and timestamps for loss sales, bill cancellations, invoice edits, and OTP-based loyalty redemptions.