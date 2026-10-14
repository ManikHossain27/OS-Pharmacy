**Only come to read this content when you work with inventory**

**Inventory Management – Detailed Functional Specification**

**1. Purpose**

The Inventory module allows pharmacy users to receive stock, define purchase and selling information, maintain batch and storage information, calculate stock quantities and purchase costs, apply inventory-level discounts, hold unfinished inventory transactions, and maintain a complete inventory history.

The module supports three inventory entry methods:

| **Mode**          | **Primary Purpose**                                                                                       |
|-------------------|-----------------------------------------------------------------------------------------------------------|
| **Default**       | Inventory entry where the user works mainly with BTP + VAT values                                         |
| **TP/VAT**        | Inventory entry where TP and VAT can be managed separately                                                |
| **Opening Stock** | Initial stock entry where inventory cost can be derived from Retail Price and an Opening Stock percentage |

**2. Main Inventory Workflow**

The high-level inventory process is:

**Select Inventory Mode → Select Product → Load Product Data → Enter Quantity/Purchase/Selling Information → Add Item to Cart → Add More Items if Required → Hold or Checkout → Apply Discount → Calculate Purchase Cost → Complete Inventory → Update Stock → Create Inventory Record/History**

An inventory transaction may contain multiple different products.

**A product can be added to an inventory cart only ONCE (updated 2026-10-07).** Adding a product that is already in the cart is refused with the message "This product is already in the cart"; the user edits the existing cart line instead, or deletes it and adds the product again. Different products can be combined freely in one inventory transaction.

**3. Inventory Modes**

The system shall provide the following three modes:

| **Mode**      | **Availability** |
|---------------|------------------|
| Default       | Required         |
| TP/VAT        | Required         |
| Opening Stock | Required         |

When the user changes the **Inventory Mode**, the **Add Items to Cart** drawer shall automatically open for that mode by default.

The user may manually close the drawer for any specific inventory mode.

The system shall remember the drawer state separately for each inventory mode. If the user closes the drawer while using a particular mode, the drawer shall remain closed when the user returns to that same mode.

The drawer state of one inventory mode shall not affect the other modes. Therefore, if the drawer is closed in one mode but has not been closed in another mode, switching to the other mode shall display the drawer in its open state.

In summary, the **open/closed state of the Add Items to Cart drawer shall be maintained independently for Default, TP/VAT, and Opening Stock modes.**

Changing the mode shall update the drawer fields and calculations according to the selected inventory mode.

**4. Common Product Selection Behavior**

When a product is selected, the system shall retrieve all relevant available product information.

At minimum, the following values shall be loaded where available:

| **Field**           | **Source**                                                     |
|---------------------|----------------------------------------------------------------|
| Qty/Box             | Product record or latest updated inventory/product information |
| Retail Price/Box    | Latest available value                                         |
| Wholesale Price/Box | Latest available value                                         |
| Product name        | Product master                                                 |
| Company             | Product master                                                 |
| Generic             | Product master, where applicable                               |
| Product type        | Product master                                                 |
| Existing barcode    | Product information where available                            |

For Retail Price/Box and Wholesale Price/Box, priority should be given to the latest relevant saved value, such as the latest inventory purchase or the value originally provided during product creation.

The loaded values are defaults only. Where the field is editable, the user may overwrite them during inventory entry.

**5. Common Quantity Logic**

**5.1 Box Quantity**

**Box Qty** represents the number of boxes being received.

**5.2 Quantity Per Box**

**Qty/Box** represents the number of individual pieces contained in one box.

The value should normally be loaded automatically from the product information or latest relevant record.

**5.3 Total Quantity**

The system shall automatically calculate:

**Total Qty = Box Qty × Qty/Box**

Example:

| **Field** | **Value** |
|-----------|-----------|
| Box Qty   | 3         |
| Qty/Box   | 10        |
| Total Qty | 30        |

If the user modifies Box Qty, Total Qty shall be recalculated.

If the user manually modifies Total Qty, Box Qty shall be recalculated using:

**Box Qty = Total Qty ÷ Qty/Box**

**Fractional Box Qty is permitted.** When Total Qty does not divide evenly by Qty/Box, the system shall accept the resulting fractional Box Qty (e.g. Total Qty = 5 with Qty/Box = 10 produces Box Qty = 0.5) rather than rounding or rejecting it. All dependent calculations (Total BTP + VAT, Total Price, and every downstream purchase-cost/payment figure) shall use the exact fractional value - not a rounded one. This applies consistently across every screen that displays Box Qty, including the Inventory Cart and Inventory Checkout tables, not only the Add Items to Cart panel and the post-completion Inventory Record / Inventory Details view.

**6. Free Quantity**

**Free Qty** represents free individual pieces supplied by the vendor in addition to the purchased quantity.

Example:

Purchased:

**10 Boxes × 20 pcs = 200 pcs**

Free Qty:

**10 pcs**

Total physical stock received becomes:

**210 pcs**

However, Free Qty shall not be treated as purchased quantity for discount calculation.

Inventory-level discounts shall **never be allocated to Free Qty**.

Free Qty therefore affects stock availability but does not receive purchase discount allocation.

**7. Default Inventory Mode**

**7.1 Purpose**

Default mode is used when purchase information is primarily entered using **BTP + VAT**.

**7.2 Default Mode Fields**

Relevant fields include:

| **Field**           | **Description**               |
|---------------------|-------------------------------|
| Company             | Product company filter        |
| Product             | Inventory product             |
| Box Qty             | Number of purchased boxes     |
| Qty/Box             | Pieces per box                |
| Total Qty           | Box Qty × Qty/Box             |
| Free Qty            | Free pieces                   |
| Total BTP + VAT     | Total BTP including VAT       |
| BTP + VAT/Box       | BTP including VAT for one box |
| Retail Price/Box    | Selling price                 |
| Wholesale Price/Box | Wholesale selling price       |
| Min Qty (pcs)       | Low-stock threshold           |
| Storage             | Rack or WHS                   |
| Batch No            | Product batch                 |
| Expiry Date         | Product expiry                |
| Barcode Value       | Product barcode               |

**8. Default Mode BTP + VAT Relationship**

The following two fields are directly linked:

**Total BTP + VAT**

and

**BTP + VAT/Box**

The calculation shall be:

**Total BTP + VAT = BTP + VAT/Box × Box Qty**

Example:

BTP + VAT/Box = Tk 50  
Box Qty = 3

Therefore:

**Total BTP + VAT = Tk 150**

If the user changes **BTP + VAT/Box**, the system shall immediately recalculate Total BTP + VAT.

If the user changes **Total BTP + VAT**, the system shall recalculate:

**BTP + VAT/Box = Total BTP + VAT ÷ Box Qty**

The values shall remain synchronized.

**10. TP/VAT Inventory Mode**

**10.1 Purpose**

TP/VAT mode allows users to manage Trade Price and VAT separately.

The general inventory behavior remains the same as Default mode.

The primary difference is purchase price input.

**10.2 TP/VAT Fields**

The inventory cart displays purchase information such as:

| **Field**           | **Description**                         |
|---------------------|-----------------------------------------|
| TP/Box              | Trade Price for one box                 |
| VAT/Box             | VAT applicable to one box               |
| Total Price         | Total purchase amount                   |
| Box Qty             | Number of boxes                         |
| Free Qty            | Free pieces                             |
| Expiry Date         | Expiry                                  |
| Other common fields | Same inventory metadata as Default mode |

**11. TP/VAT Automatic VAT Calculation**

When the user enters **TP/Box**, the system shall automatically calculate VAT/Box using the configured VAT percentage.

For the current TP/VAT mode requirement:

**System VAT = 17.4%**

Example:

If:

**TP/Box = Tk 100**

then VAT/Box shall initially be calculated using the system VAT percentage.

The VAT/Box field shall remain editable.

If the user manually changes **VAT/Box**, the system shall accept the manually entered VAT amount.

Importantly:

**Changing VAT/Box shall NOT modify TP/Box.**

TP/Box remains the user-entered trade price.

**12. Optional TP/VAT Values**

In TP/VAT mode:

**TP/Box is optional.**

**VAT/Box is optional.**

The inventory transaction shall therefore be allowed even when TP is not entered.

Example:

TP/Box = 0  
VAT/Box = Tk 5

The inventory may still be completed.

In such cases, purchase-price calculations shall use the available values rather than preventing inventory creation.

**13. TP/VAT Total Price**

For each box:

**Box Purchase Amount = TP/Box + VAT/Box**

For purchased boxes:

**Total Purchase Amount = (TP/Box + VAT/Box) × Box Qty**

**14. Opening Stock Mode**

**14.1 Purpose**

Opening Stock mode is designed primarily for entering stock already available when the pharmacy begins using the system or when stock needs to be initialized.

Opening Stock mode uses an **Opening Stock (%)** value to derive the stock cost from the retail selling price.

**15. Opening Stock Percentage**

The default Opening Stock percentage shall initially be:

**12%**

The percentage shall be automatically populated when Opening Stock mode is selected.

The user may overwrite the percentage.

Example:

Opening Stock (%) = 12%

The system shall use the entered percentage together with Retail Price/Box to calculate the initial BTP + VAT/Box value according to the approved Opening Stock pricing formula.

Because the exact mathematical relationship between the 12% value and Retail Price/Box has not yet been explicitly defined in the provided business rules, the development specification should preserve this as a configurable pricing rule rather than assume whether 12% is a markup, margin, deduction, or another calculation basis.

**16. Opening Stock Product Selection**

When the user selects a product in Opening Stock mode, the system shall automatically retrieve:

| **Data**            |
|---------------------|
| Qty/Box             |
| Retail Price/Box    |
| Wholesale Price/Box |

After loading Retail Price/Box, the system shall automatically calculate BTP + VAT/Box using the current Opening Stock percentage.

This calculation should happen immediately after product selection when all required source values are available.

**17. Opening Stock Quantity Calculation**

The standard quantity relationship applies:

**Total Qty = Box Qty × Qty/Box**

Example:

Qty/Box = 20  
Box Qty = 5

Total Qty: **100 pcs**

**18. Opening Stock BTP Calculation**

The system shall first calculate:

**BTP + VAT/Box**

using:

**Retail Price/Box + Opening Stock (%) calculation rule**

The resulting BTP + VAT/Box shall then be used to calculate:

**Total BTP + VAT = BTP + VAT/Box × Box Qty**

The calculated BTP + VAT/Box remains editable.

**19. Manual Override in Opening Stock**

The user may directly overwrite the calculated **BTP + VAT/Box**.

Once manually overwritten, the system shall use the manually entered amount rather than forcing the 12% calculation again. And Opening Stock (%) value will be auto calculated by overridden BTP+VAT/Box amount.

The Total BTP + VAT shall then become: **Manual BTP + VAT/Box × Box Qty**

Example:  
Retail price =100

Box Qty = 10  
Manually entered BTP + VAT/Box = Tk 80

Total: **Tk 800  
**Opening Stock (%) will be 20

A change in Box Qty shall continue to update Total BTP + VAT.

**20. Retail Price**

Retail Price/Box represents the box-level selling price.

It is not the purchase price.

If a Retail Price exists from a previous inventory transaction or product creation record, it shall automatically appear after selecting the product.

The user may modify the value.

For Opening Stock specifically, changing Retail Price/Box shall trigger recalculation of BTP + VAT/Box when the BTP value is still system-calculated rather than manually overridden.

**21. Wholesale Price**

Wholesale Price/Box represents the wholesale selling price for the product.

If previously available, the system shall automatically load the latest applicable value.

The user may update the value during inventory entry.

The updated value should become available for subsequent relevant product/inventory operations according to the product price persistence rules.

**22. Minimum Quantity and Low Stock**

**Min Qty (pcs)** represents the low-stock threshold for a product.

A product shall be considered Low Stock when:

**Available Qty ≤ Min Qty**

Example:

Min Qty = 20 pcs  
Available Qty = 20 pcs

Status: **Low Stock**

Available Qty = 15 pcs

Status: **Low Stock**

Available Qty = 21 pcs

Status: **Not Low Stock**

Products identified as Low Stock shall appear on the **Requisition Shortlist** page.

**23. Storage**

The Storage field shall support two storage types:

| **Type**        | **Behavior**                                       |
|-----------------|----------------------------------------------------|
| Rack            | User can provide/select the rack information (str) |
| WHS / Warehouse | No input - a pharmacy has a single warehouse, so the text field is intentionally disabled when WHS is selected (confirmed 2026-10-08) |

The storage information belongs to the inventory item/batch.

Each inventory batch carries its own storage information.

**24. Batch Number**

Batch No is optional during inventory entry.

If the user enters a Batch No, the system shall use the provided value.

If Batch No is left empty, the system shall automatically generate a batch number when the inventory item/transaction is created.

The generated number must uniquely identify the appropriate inventory batch according to the system's batch-numbering convention.

**25. Expiry Date**

Expiry Date represents the expiration date of the received product batch.

Where applicable, it shall be stored against the corresponding inventory/batch record.

Each inventory batch carries its own expiry date (one cart line per product per inventory).  
If user don’t pass any expiry dates, that means this batches’ product will be valid for life time. Product Sale will be followed FEFO (First Expiry First Out).

**26. Barcode**

The user may enter a Barcode Value for the inventory item/product.

Where an existing barcode is available from product information, the system may preload the existing value according to the product-data rules.

Any barcode update must follow the product's barcode uniqueness and persistence rules.

**27. Add Items to Cart**

After entering the required item information, the user shall click: **Add Items to Cart**

The item shall then be added to the Inventory Cart.

Adding an item does not yet finalize inventory.

**28. Multiple Cart Items**

The Inventory Cart shall support:

Multiple different products within one inventory transaction.

One cart line per product (a second add of the same product is refused - see section 2).

Example: Napa (batch B001, expiry Dec 2027, 10 boxes) and Paracetamol (batch B002, expiry Mar 2028, 5 boxes) are two valid cart lines. Adding Napa a second time - even with a different batch or expiry - is refused ("This product is already in the cart"); to receive Napa in a different batch, complete the current inventory and create another one.

**29. Inventory Cart Information**

Depending on the selected Inventory Mode, the inventory cart shall display relevant information such as:

| **Information**           |
|---------------------------|
| Product details           |
| Box Qty                   |
| Total Price               |
| TP/Box                    |
| VAT/Box                   |
| BTP + VAT                 |
| Expiry                    |
| Free Qty                  |
| Opening Stock information |
| Edit action               |
| Delete action             |

The displayed purchase columns shall adapt to the selected inventory mode.  
  
When the **Add Items to Cart** side drawer is open, the cart may use a more compact layout because part of the screen is occupied by the drawer.

When the user closes the **Add Items to Cart** side drawer, the Inventory Cart shall expand and display additional item information.

In the expanded cart view, the system shall display the above information together with:

| **Additional Information** |
|----------------------------|
| Current Stock in Pieces    |
| Current Stock in Boxes     |
| Retail Selling Price       |
| Wholesale Selling Price    |
| Storage Information        |

This expanded view shall provide the user with a more complete overview of each inventory item without requiring the item to be opened or edited.

**30. Edit Cart Item**

The user shall be able to edit an existing inventory cart item.

When Edit is selected, the item's existing information shall load into the Add Items drawer.

The UI must clearly communicate that the user is editing an existing cart item rather than creating a new one.

The exact visual implementation may vary, but the editing state must be unmistakable.

Saving shall update the existing cart record rather than create another entry.

**31. Delete Cart Item**

The user shall be able to delete an individual item from the Inventory Cart.

Deleting one item shall not affect other cart items.

Totals shall immediately recalculate after deletion.

**32. Inventory Total**

The inventory page shall display the current total inventory purchase amount.

This represents the total purchase value including applicable VAT for purchased items.

Free Qty shall not incorrectly increase the purchased TP amount.

**33. Hold Inventory**

After at least one product has been added to the inventory cart, the user may choose:

**Hold Current Inventory**

Holding inventory shall preserve the unfinished transaction.

The held record must retain all entered details including quantities, prices, batches, expiry information, free items, storage information, and other inventory-level information.

The user shall be able to resume the held inventory later and continue editing or checkout.

**34. Hold List**

Held inventory transactions shall appear in the Hold List.

When a held inventory is resumed, the user shall receive the previously saved cart state.

Completing a held inventory shall remove or appropriately mark the corresponding Hold List record as completed.

**35. Inventory Checkout**

When the cart contains inventory items, the user may proceed to:

**Go to Inventory Checkout**

Checkout is responsible for final purchase calculations and discount allocation before stock is committed.

**36. Checkout Total Price**

The checkout page shall show the:

**Total Price**

This represents the total pre-discount purchase amount of the eligible inventory items.

**37. Inventory Discount**

Inventory checkout shall support at least:

| **Discount Type** | **Example** |
|-------------------|-------------|
| Percentage        | 10%         |
| Flat              | Tk 500      |

The entered discount generates a **Final Discount Amount**.

The final discount amount shall be allocated against the **TP component** of purchased stock.

It shall not reduce VAT directly unless otherwise required by future accounting/tax rules.

It shall not apply to Free Qty Product.

**38. Discount and Free Quantity**  
If a product has any **Free Qty**, that product shall be excluded from inventory discount distribution.

Example: If an inventory has 5 products and **Napa** includes 10 free pcs, the discount shall apply only to the other 4 products.

Discount basis:

| **Mode**      | **Discount Applies On** |
|---------------|-------------------------|
| TP/VAT        | TP amount               |
| Default       | BTP + VAT amount        |
| Opening Stock | BTP + VAT amount        |

Free Qty increases physical stock and reduces the effective purchase price per piece.

Example:

- Qty/Box = 10 pcs

- TP/Box = Tk 15

- VAT/Box = Tk 10

- Box Qty = 2

- Purchased Qty = 20 pcs

- Free Qty = 10 pcs

- Total Physical Qty = 30 pcs

Purchase price per piece:

**{(15 + 10) × 2} ÷ 30 = Tk 1.66**

Without the Free Qty, the purchase price would be:

**Tk 50 ÷ 20 = Tk 2.50 per piece**

> **Clarification (verified in the workbook sheet and the application, 2026-10-11):** in TP/VAT mode the VAT of the free pieces is charged as well - Total = (TP/Box + VAT/Box) × Box Qty + (VAT/Box ÷ Qty per Box) × Free Qty. For the example above the total is (15 + 10) × 2 + 1.00 × 10 = Tk 60 and the purchase price per piece is **60 ÷ 30 = Tk 2.00**.

**39. Discount Distribution**

When an inventory contains multiple products, the **final discount amount shall be distributed only among eligible products that do not have any Free Qty**.

Products with **Free Qty shall be completely excluded from discount allocation**.

The allocation must ensure:

**Sum of all eligible item-level allocated discounts = Checkout-level final discount amount**

Rounding must be handled so that no financial discrepancy remains between the checkout total and the sum of inventory-line costs.

The exact proportional allocation algorithm should be fixed during technical implementation if it has not already been defined by the existing backend.

**This distribution basis applies identically to both Discount Types (Percentage and Flat).** When the checkout-level discount is entered as a Flat (Tk) amount, that amount shall be distributed across eligible products proportionally based on each product's purchase price, using the same allocation logic already described above for a Percentage discount - Free-Qty lines remain fully excluded either way.

Regardless of which Discount Type was entered at checkout (Percentage or Flat), **each eligible product's allocated share shall be displayed on the Inventory Details view as a percentage (%) of that product's purchase price** - not as a Tk amount. This is the correct, by-design display for the per-product breakdown; the checkout-level Discount Type selector only controls how the user enters the overall discount, not how each line's resulting allocation is expressed afterward.

**40. Purchase Price**

**The final purchase price shall be calculated as:**

**Purchase Price = TP − Allocated Discount + VAT**

**At unit level:**

**Unit Purchase Price = Unit TP − Unit Allocated Discount + Unit VAT**

**If the product has Free Qty, it will not receive any discount. The purchase cost shall be distributed across the total physical quantity, including free items.**

**Purchase Price per Piece = {(TP/Box + VAT/Box) × Box Qty} ÷ Total Qty including Free Qty**

**Example: If 10 pcs are received free, those free pieces reduce the effective purchase price per piece.**

**41. Inventory Without TP**

The system must support inventory transactions where TP is not provided.

Example:

TP = Tk 0  
VAT = Tk 5

Then the system shall not reject inventory solely because TP is zero.

Purchase price shall be calculated from the available values.

Conceptually:

**Purchase Price = 0 − 0 + VAT**

Therefore, the applicable VAT amount may effectively become the purchase price where no TP or discount exists.

**42. Final Inventory Completion**

On successful checkout, the system shall:

| **Required Result**                           |
|-----------------------------------------------|
| Complete the inventory transaction            |
| Add received quantities to stock              |
| Add Free Qty to physical stock appropriately  |
| Create/update corresponding batch information |
| Store purchase costing                        |
| Store discount allocation                     |
| Store VAT information                         |
| Store retail/wholesale prices                 |
| Store storage information                     |
| Store expiry information                      |
| Store batch information                       |
| Store barcode information where applicable    |
| Update low-stock status                       |
| Generate inventory history/record             |

Stock shall not be permanently added merely because the item exists in the temporary Inventory Cart.

Stock becomes committed when inventory is successfully completed.  
  
**42.1. Inventory Completion Success Modal**

After a successful inventory creation, the system shall display an **Inventory Complete** success modal.

The modal shall show:

| **Information**            |
|----------------------------|
| Inventory ID               |
| Inventory Details link     |
| Supplier Information       |
| Payment Status: Paid / Due |
| Inventory Type             |
| Total Items                |
| Total Price                |
| Discount                   |
| Final Price                |
| Total Paid                 |
| Due Amount                 |

The modal shall also provide the following actions:

- **Invoice**

- **Hold List**

- **New Inventory**

The **Inventory Details** link shall open the completed inventory record for review.

**43. Inventory Record**

After inventory completion, a corresponding transaction shall appear under:

**Inventory Record**

The record shall accurately reflect the completed inventory transaction.

Relevant values should include the transaction-level information and item-level history necessary to audit the inventory.

**44. Inventory History Verification**

After every completed inventory, the system should allow verification of:

| **Area**        | **Verification**                    |
|-----------------|-------------------------------------|
| Product         | Correct product                     |
| Qty             | Correct purchased quantity          |
| Free Qty        | Correct free quantity               |
| Stock           | Correct available quantity increase |
| Box Qty         | Correct box quantity                |
| Qty/Box         | Correct conversion                  |
| TP              | Correct TP                          |
| VAT             | Correct VAT                         |
| Min Qty         | Correct Minimum Qty allocation      |
| Discount        | Correct allocation                  |
| Purchase Price  | Correct final cost                  |
| Retail Price    | Correct selling price               |
| Wholesale Price | Correct selling price               |
| Batch           | Correct or generated batch          |
| Expiry          | Correct expiry                      |
| Storage         | Correct Rack/Warehouse              |
| Barcode         | Newly generated Barcode             |
| Inventory mode  | Correct source mode                 |
| Inventory total | Matches checkout                    |
| History         | Complete and traceable              |

**44.1 Inventory Details View — Required Fields**

The **Inventory Details** view (opened from Inventory Record to review a completed inventory transaction) is the primary screen through which the verification areas listed in section 44 are actually carried out. To satisfy section 44, this view shall display the following, at minimum:

**Inventory Details**

| **Field**                |
|---------------------------|
| Inventory ID              |
| Supplier Name             |
| Supplier Phone Number     |
| Inventory Date & Time     |
| Received By               |

**Pricing Breakdown**

| **Field**                          |
|-------------------------------------|
| Total Items                         |
| Total Price                         |
| Total TP Price                      |
| VAT Amount                          |
| Discount Amount (on TP Price)       |
| Final Price                         |
| Total Paid (with payment method(s)) |
| Payment Status                      |

**Inventory Items (per line item)**

| **Column**       |
|-------------------|
| Details (product) |
| Batch / Expiry     |
| Rack / Storage     |
| Qty                |
| Qty/Box            |
| Free               |
| BTP + VAT          |
| Discount           |
| Price (shows Total and Final) |
| Purchase Price     |
| Retail Price       |
| Whole Sale Price   |

Note (2026-10-07): Min. Qty and Barcode are not shown on this view, and an item's Total Price is shown in the Price column under the label "Total" (with "Final" beside it). Free Qty is shown in the Qty column as "N pc free".

All values shown in this view shall be sourced from the completed inventory record (not recomputed client-side) and shall match the corresponding stored values described in sections 42 and 44 — including, where a discount was applied, item-level Purchase Price and Total Price that reflect the allocated discount per section 39-40, not the pre-discount BTP+VAT figures.

**Inventory Type and Supplier Payment**

The system shall support two Inventory Types: Purchase, Borrow

Inventory Type is separate from the Inventory Mode.

From Inventory Checkout, the user shall be able to select an existing supplier or Add New Supplier if the supplier is not available in the supplier list.

The user shall be able to enter the supplier's Invoice Number and record supplier payments using:

Cash, Card, Bank, MFS

Multiple payment methods may be used within the same inventory transaction. For example, part of the payment may be made by Cash and the remaining amount by Bank or MFS.

The Paid Amount may be less than, equal to, or greater than the invoice/final amount.

Based on the current inventory amount, payment made, and the supplier's existing balance, the system shall calculate and update the supplier's:

Paid Amount, Due Amount, or Advance Amount.

If the payment is lower than the payable balance, the remaining amount shall be recorded as Due. If the payment exceeds the payable balance, the additional amount shall be recorded as Supplier Advance.

When Total Paid differs from the Final Price, Complete Inventory shall ask the user how to settle the difference (verified 2026-10-11): if less was paid - **Due & Buy** (the short amount stays Due to the supplier) or **Less & Buy** (the short amount is waived; the products cost less and the supplier balance does not change); if more was paid - **Advance & Buy** (the extra becomes Supplier Advance). The inventory is created only after one of these is chosen. Supplier balance after = balance before + Final Price - Paid - Less.

**45. Calculation Dependency Matrix**

| **User Changes**                      | **System Must Update**                                                 |
|---------------------------------------|------------------------------------------------------------------------|
| Product                               | Qty/Box, Retail Price, Wholesale Price and relevant stored information |
| Box Qty                               | Total Qty                                                              |
| Total Qty                             | Box Qty                                                                |
| BTP + VAT/Box                         | Total BTP + VAT                                                        |
| Total BTP + VAT                       | BTP + VAT/Box                                                          |
| TP/Box in TP/VAT mode                 | VAT/Box automatically using system VAT                                 |
| VAT/Box manually                      | TP/Box must remain unchanged                                           |
| Retail Price in Opening Stock         | Recalculate BTP + VAT/Box using Opening Stock %                        |
| Opening Stock %                       | Recalculate BTP + VAT/Box                                              |
| Manual BTP + VAT/Box in Opening Stock | Recalculate Total BTP + VAT and update Opening Stock %                 |
| Box Qty after manual BTP override     | Recalculate Total BTP + VAT                                            |
| Cart item added/deleted/updated       | Recalculate inventory totals                                           |
| Checkout discount                     | Recalculate allocated discount and purchase price                      |

**46. Core Validation Requirements**

The system shall prevent mathematically invalid inventory states while still supporting valid zero-cost scenarios.

| **Field/Condition**         | **Expected Validation**                    |
|-----------------------------|--------------------------------------------|
| Product                     | Required                                   |
| Box Qty                     | Required and must be greater than 0 (0 is not acceptable; confirmed 2026-10-08) |
| Qty/Box                     | Must be valid for quantity calculations    |
| Total Qty                   | Must remain consistent with quantity logic |
| Negative quantity           | Not permitted                              |
| Free Qty                    | Cannot be negative                         |
| Negative price              | Should not be permitted                    |
| Min Qty                     | Cannot be negative                         |
| Past expiry date            | Allowed - intentional (confirmed 2026-10-08) |
| Empty Batch                 | Allowed; system generates one              |
| TP = 0                      | Allowed                                    |
| VAT = 0                     | Allowed                                    |
| Retail/Wholesale override   | Allowed according to mode                  |
| Same product twice in one cart | Not allowed - one line per product (message: "This product is already in the cart") |

**47. Important Business Rules**

The most important rules for implementation are:

1.  **Three inventory calculation modes must remain independent while sharing common inventory behavior.**

2.  **Box Qty, Qty/Box and Total Qty must always remain logically synchronized.**

3.  **Default mode manages BTP + VAT.**

4.  **TP/VAT mode allows independent manual VAT adjustment without modifying TP.**

5.  **Opening Stock initially derives BTP + VAT/Box from Retail Price and Opening Stock percentage but permits manual BTP override.**

6.  **Free Qty adds stock, but this product will not receive any purchase discount.**

7.  **Discount is allocated against TP for TP/BAT mode, for Default and Opening stock it will allocated against TP+VAT.**

8.  **Final purchase cost follows TP − Discount + VAT.  
    At unit level, Unit Purchase Price = Unit TP − Unit Allocated Discount + Unit VAT  
    if receive free qty of a product, Purchase price = {(TP/box + Vat/box) \* Box Qty}/ total Qty including free qty.**

9.  **A product can appear only once in an inventory cart (updated 2026-10-07).**

10. **Low stock occurs when Available Qty ≤ Min Qty and must feed the Requisition Shortlist.**

11. **Inventory may be held and resumed later.**

12. **Every successful inventory must create accurate, traceable inventory history.**

**48. Items That Need Exact Business-Rule Confirmation**

There is one remaining area where your explanation defines the required behavior but does not yet give enough information to lock down the exact mathematical implementation.

| **Area**                  | **Confirmation Needed**                                                                    |
|---------------------------|--------------------------------------------------------------------------------------------|
| **Opening Stock 12%**     | Exact formula converting Retail Price/Box and Opening Stock % into BTP + VAT/Box           |

~~**Total Qty override** — What happens when Total Qty ÷ Qty/Box produces a fractional Box Qty~~ - **Resolved 2026-09-15**: fractional Box Qty is permitted; see section 5.3.

~~**Discount distribution** — Exact proportional/allocation method when multiple products with different TP values exist~~ - **Resolved 2026-09-15**: distribution is proportional by purchase price, applies identically to Percentage and Flat discount types, and each product's allocated share always displays as a percentage on Inventory Details regardless of the entered Discount Type; see section 39.


**Borrow-Type Inventory Behaviour**

From **Inventory Checkout**, the user can select **Borrow**
as the Inventory Type.

After successfully completing a Borrow-type inventory:

- The inventory shall be recorded normally and stock shall be added.
- The Borrow inventory shall **not be treated as the productâ€™s last inventory/purchase record**.
- It shall **not update the productâ€™s reference values**, such as **BTP + VAT/Box, Total BTP + VAT, Retail Price/Box, Wholesale Price/Box, Qty/Box**, or other values normally carried forward from the latest inventory.

When the user creates another inventory for the same
product, the **Add Items to Cart** drawer shall preload data from the latest
eligible **non-Borrow inventory record** or the existing product record, not
from the Borrow inventory.

---

**Inventory Cancellation and Inventory Return**

**Inventory Cancellation**

A completed inventory can be **cancelled only if no item
from that inventory batch has been sold**.

When an inventory is cancelled, the entire transaction shall
be reversed:

- Inventory/stock quantity shall decrease.
- Inventory amount shall be reversed.
- Cash, Card, Bank, MFS, or other payment balances affected by the original inventory shall be restored accordingly.
- Supplier balance shall also be reversed accordingly.

The cancellation should return the system to the financial
and stock position that existed before the inventory was created.

---

**Inventory Return**

Products can be returned only when the corresponding **inventory
batch still has available quantity**.

The user can initiate a return in two ways:

- From a specific **Inventory Record**.
- From the dedicated **Inventory Return** menu.

When returning from a specific Inventory Record, only
products and available quantities belonging to that inventory shall be
returnable.

**Return from Inventory Return Menu**

The user shall:

1. Select a product.
2. View only the available batches for that product.
3. Select a batch.
4. View the available quantity of that batch.
5. Enter the Return Qty as **Pieces or Boxes**.
6. Click **Add to Return Cart**.

**Inventory Return Cart**

The Return Cart shall display:

- Product
- Return Qty
- If returned by Box, total return quantity in pieces
- Batch No.
- Expiry Date
- Purchase Price per Piece or Purchase Price per Box
- Total Return Price
- Edit action
- Delete action

The user may edit or remove items before checkout.

---

**Return Checkout**

During Return Checkout, the user shall select the **Supplier**.

If the return is initiated from a specific Inventory Record,
the related supplier shall be **pre-selected**.

The user may apply **Demurrage** as:

- Percentage (%)
- Flat Amount

The final return amount shall be calculated after applying
Demurrage.

Based on the final return amount:

- The amount shall be added to the **Pharmacy Wallet**.
- The **Supplier Balance** shall be updated accordingly.
- Returned stock quantity shall be deducted from the related batch.

---

**Return Details and Return Cancellation**

The **Return Details** page shall display complete
information about the return transaction, including products, batches,
quantities, prices, demurrage, supplier, and final return amount.

The user shall also be able to **Cancel a Return**.

When a return is cancelled, the entire return transaction
shall be reversed:

- Returned quantity shall be restored to stock.
- Pharmacy Wallet adjustment shall be reversed.
- Supplier balance adjustment shall be reversed.
- All related financial effects shall return to their previous state.

All completed inventory returns shall be available in the **Inventory
Return Record**.

**Stock Adjustment**

Stock Adjustment shall follow a flow similar to **Inventory
Return**, but it is used for inventory loss rather than supplier returns.

The user shall select one of the following **Adjustment
Types**:

- **Missing**
- **Destroyed**

The user can select a product, choose an available batch,
view the available batch quantity, and enter the adjustment quantity in **Pieces
or Boxes**. The item can then be added to the Stock Adjustment Cart, where it
can be edited or deleted.

Unlike Inventory Return:

- There shall be **no Demurrage**.
- There shall be no supplier return amount.
- The adjusted quantity shall be deducted from the related inventory batch.
- The corresponding inventory value shall be reduced from the **Inventory Balance**.
- The same amount shall be recorded as a **Business Loss**.

In summary:

**Stock Adjustment Amount = Inventory Value Reduction =
Business Loss**

The Stock Adjustment record shall retain the product, batch,
quantity, purchase price, total loss amount, and adjustment type (**Missing/Destroyed**).



**Supplier Management**

The system shall allow users to create and manage suppliers.

**Create Supplier**

To create a supplier, the user can enter:

- Supplier Name
- Phone Number
- Opening/Supplier Balance
- Balance Type: **Due or Advance**
- Note, if required
- Status: **Active or Inactive**

The user shall also be able to change a supplier between
Active and Inactive status.

---

**Supplier List**

The Supplier List shall display summary information such as:

- Total Suppliers
- Active Suppliers
- Total Due
- Total Advance

For each supplier, the table shall display:

- Supplier Name
- Phone Number
- Total Purchases
- Total Purchase Value
- Current Balance
- Balance Type: Due / Advance
- Status
- Actions

Users shall be able to:

- Search by supplier name or phone number
- Filter by status
- Filter **Due suppliers**
- Filter **Advance suppliers**
- Reset filters

---

**Supplier Payment**

The user shall be able to create a supplier transaction
with:

- Payment Type:
  - **Payment**
  - **Return**
- Amount
- Payment Method
- Note

If OTP verification is required, the user must verify the
transaction using the OTP received by SMS before confirming the payment.

**Payment**

When Payment is selected:

- Pharmacy balance shall decrease.
- Supplier balance shall increase.
- The updated supplier balance shall be shown after the payment.

**Return**

When Return is selected:

- Supplier balance shall decrease.
- Pharmacy balance shall increase.
- The updated supplier balance shall be shown after the transaction.

---

**Supplier Ledger**

The user shall be able to view a complete **Supplier Ledger**.

The ledger shall display:

- Supplier Name
- Phone Number
- Opening Balance
- Reference ID
- Transaction Date
- Transaction Type
- Description
- Debit
- Credit
- Running Balance
- Closing Balance

The ledger shall include transactions such as:

- Purchases
- Supplier Payments
- Supplier Returns
- Other supplier balance adjustments

Users shall also be able to search/filter ledger records and
**Download the Supplier Ledger**.