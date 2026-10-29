# Sale Management - exploration, test cases and findings

Source of truth: `Knowledge/Sale Management/Sale management.md` (SRS). Environment: staging `pms-sql-portal.ems24.co`, pharmacy **Manik Pharma** (pharmacy id 598), role Owner, tested 2026-10-27 with Playwright MCP (Chromium).
Nothing was saved, completed or submitted during exploration: the cart was filled and cleared client-side only, no sale was completed, no customer created, no setting changed.

**Status legend:** `Pass` / `Fail` = executed on staging; `Not run` = designed, needs the data/setting listed in *Pre*; `Blocked` = needs a requirement answer first (see Gaps).

## 1. Modules and routes explored

| Area | Route | Observed |
|---|---|---|
| Sale (POS) | `/sale` | Product search, Qty + Pcs/Box, Sale Price, Discount (%/Tk), Add to Cart, Retail/Wholesale mode, Hold List (0), Hold Current Sale, cart persists across reload |
| Sale Checkout | `/sale-checkout` | Walk-in / Choose Customer, Add New Customer, Discount, Round Off, Final Price, Customer Paid + method (CASH...), Due, Card Commission, Cash Received, Note, Quick Print (unchecked by default), Complete Sale |
| Sale Record | `/sale-record` | Tiles (Total Sales, Collected, Profit, Due); filters Search, Date Range, Status, Payment Method, Channel, Sold By, Reset; paging |
| Customer List | `/customer` | Tiles; tabs All / Due / Advance / Loyalty; Add New Customer drawer |
| Cashier | `/cashier` | "Waiting in Queue", Complete all, search |
| Sale Return / Record | `/sale-return`, `/sale-return-record` | Search invoice, Sale Qty / Return Qty / Batch-Expiry, Go to Return Checkout |
| Due Collect | `/due-collect` | Today / Upcoming / Overdue / Paid tabs, date range |
| Settings | `/settings/sale-config`, `/settings/loyalty-config`, `invoice-config`, `product-config`, `bulk-sms-config` | see below |
| Dashboard | `/dashboard` | Sale Summary, Profit, Customer Due, Staff Performance, Sales Trend, Product Movers, Treasury |
| Products / Inventory | `/my-products`, `/product-catalog`, `/inventory` | supply the stock, batches, Pcs/Box and prices the POS uses |

**Manik Pharma starting state:** Sale Config - all 7 toggles OFF, Business Type Retail (API `sales-configs/598`: `outOfStockSale/allowLossSale/stockQty/companyName/profitMargin/rackNo/separateCashier = false`). Loyalty Config - all four values 0. Customers: 1 (Manik Hossain, +8801521503629, loyalty member, 0 pts, balance 0, added by the tester; none at first look). Sale Record: 0 sales. Held sales: 0. Cashier queue: 0.
**Add Customer fields:** Name\*, Phone\* (+880), Address, Balance (Advance/Due), Discount %, Due Payment Date, Status (Active), Loyalty Member (Inactive), Note.
**Environment note:** the staging host runs a Vite dev server; every page logs 3 console errors about the HMR websocket (`wss://localhost:5000`). Not a product defect, ignored.

## 2. Dependencies (what other modules must provide)

| Needs | From | Why / check |
|---|---|---|
| Products with batches, expiry, Pcs/Box, last purchase price, retail & wholesale price | Products + Inventory | FEFO, COGS, loss-sale check, price auto-fill. Verify product price/Pcs-per-Box edits flow into POS |
| Stock quantity | Inventory / Stock Adjust | Out-of-stock rule, stock display, negative stock |
| Sale Config / Loyalty Config / Invoice Config | Settings | every toggle changes POS behaviour; changes must apply without re-login |
| Payment methods | Customizations > Payment Methods | split-payment tenders |
| Customers, due, advance, points | Customer List | Registered flow, ledger |
| Treasury / Cash Closer / Cashbook | Accounting | each completed sale, due collection, return must move treasury |
| Dashboard / Analytics / Sale Record / Due Collect | Reporting | totals must agree with each other and the sale |
| Roles | User Management | cashier vs salesperson vs owner access (unverified - only Owner was available) |

## 3. Findings (verified on staging)

| ID | Sev | Title | Evidence |
|---|---|---|---|
| BUG-SALE-001 | High | With **Out of Stock Sale OFF**, products with 0 stock appear in search and can be added to the cart | `/sale`, search "napa": 5 results all `0 pcs 0 box`; NAPA 500 MG added x5 pcs, cart total Tk 6.00, "Go to Sale Checkout" enabled. API config confirms `outOfStockSale:false`. Screenshots `sale-search-oos-off.png`, `sale-cart-oos.png` |
| BUG-SALE-002 | Medium | With **Stock Qty OFF**, stock is still shown in search options and in the cart "Stock" column | `0 pcs / 0 box` visible in dropdown and cart; API `stockQty:false` |
| BUG-SALE-003 | Low | With **Company Name OFF**, the company is still shown in search options and under the selected product | "BEXIMCO PHARMACEUTICALS LTD." in dropdown and product detail line; API `companyName:false` |
| BUG-SALE-004 | Medium (confirmed by tester) | Dashboard is self-contradictory: Sale Summary "Sales Tk 0 / Profit Tk 0" (Today) while Staff Performance lists 7 invoices, Tk 4,823 revenue, Tk 1,308 profit; Sale Record shows 0 sales with no date filter | Needs retest: confirm whether Staff Performance ignores the period or counts other pharmacies |
| BUG-SALE-005 | Low | Dashboard "Expiring Stock" shows `1 Jan 1970 - expired 20753d ago` for batches without an expiry date | Epoch date rendered instead of "No expiry" |
| BUG-SALE-006 | High | **Customer Details drawer shows another customer's data**: for Manik Hossain it shows "Nusrat Jahan", 01912-345680, Advance Tk 2,600, 10 % discount, 11 points, 3 orders / Tk 21,400 and recent invoices INV-100234/198/121 | `/customer` > row menu > View Details. Opening the drawer makes **no API call** (only the list load does); `GET customers/598` returns Manik Hossain with points 0, orders 0, discount 0. Screenshot `cust-details.png` |
| BUG-SALE-007 | High | **Customer Ledger shows fabricated entries**: 7 records (#INV-31, #INV-32, #PAY-CUS-33..37, "Sale on credit", "Test of due payment"), opening balance "Tk 100 Cr", for a customer with 0 orders and Tk 0 balance; the running balance also does not follow from the rows | Same session, **no ledger API call**; header name/phone are right, rows are hard-coded demo data. Screenshot `cust-ledger.png` |
| OBS-SALE-006 | Info/Gap | `/cashier` queue page opens normally while Separate Cashier is OFF | SRS does not say it should be hidden |
| OBS-SALE-007 | Info/Gap | Cart item delete (trash icon) has no confirmation | SRS silent |
| OBS-SALE-008 | Low | Checkout discount accepts 150 % and -5 in the box and silently ignores them (amount stays Tk 0.00, no message) | Calculation is safe, feedback is missing |
| OBS-SALE-009 | Info/Gap | "Apply Max Loyalty Points" button is shown for a loyalty customer with 0 points while the loyalty config is all 0 | Not clicked: it may send an OTP SMS |
| BUG-SALE-008 | High | **Walk-in overpayment is recorded as "Advance" and the surplus is kept**: paying Tk 130 on a Tk 100 walk-in sale shows the dialog "Return Tk 30.00 cash change... Net sale settles at Tk 100.00", but Sale Details shows Total Paid Tk 130, status Advance, profit unchanged (85.36); Treasury cash +130; Dashboard profit includes the extra Tk 30 (351 vs Sale Record 321) | Sale #SALE_20261027_03; SRS 4.4: walk-in overpay = Profit & Sale (surplus added to profit, no advance) |
| BUG-SALE-009 | High | **Sale Return cash refund is not deducted from Treasury / Cash Closer**: returning 1 pc (refund Tk 40) left Cash Tk 3,29,740, "out Tk 0", Total Treasury 33,23,620 and Cash Closer expected Tk 385 unchanged | Return of #SALE_20261027_02; a cancel of a sale DID reverse Tk 100 correctly |
| BUG-SALE-010 | Medium | **Sale Record tiles still count a cancelled sale**: after Cancel Sale the tiles stay at Total Sales (5) Tk 410, Collected Tk 385, Profit Tk 289 although the confirm text says it is left out of totals; Dashboard does exclude it (Sales Tk 280) | Sale #SALE_20261027_01 |
| BUG-SALE-011 | Medium | **Return uses the SALE id sequence and is counted as a sale**: the return is listed as #SALE_20261027_05, Sale Record shows Total Sales (5) with 4 real sales, and the Sale Return Record tile reads "Total Sales (1) / Tk 0" for a Tk 40 return | Return of #SALE_20261027_02 |
| BUG-SALE-012 | Medium | **A customer due with no due date is invisible in Due Collect**: Total due (1) Tk 40 but the Today / Upcoming / Overdue tabs are all empty ("No due found for today") | Due & Sale #SALE_20261027_04 |
| BUG-SALE-013 | Medium | **Searching `%` crashes the list**: Customer List freezes in a greyed state and Sale Record renders a blank page; `URIError: URI malformed` in `normalizeQueryParams` (`useQueryParams.ts`) for `?searchKey=%25` | Same pattern as the Product Catalog crash; `catalog-percent-search-crash.png` |
| BUG-SALE-014 | Medium | **POS Sale Mode toggle changes the pharmacy-wide Business Type**: clicking Wholesale sends `PUT sales-configs/update/598` and the saved config became `businessType: WHOLESALE` for every session; restored to RETAIL afterwards | Found because a parallel session switched the other browser to Wholesale |
| BUG-SALE-015 | Low | **Sale Details has no batch breakdown**: shows Cost Tk 14.64 / 7.32 per pc but no batch or expiry although SRS 7.1 says "full breakdown of batches, costs..." | View Details of #SALE_20261027_01 |
| BUG-SALE-016 | Low | **Cart silently accepts or reshapes invalid input**: Qty 0 / -1 ignored with no message; 0.5 becomes 1 and 2.5 becomes 3; Qty 99,99,99,999 accepted while stock is 1,08,413 and Out of Stock Sale is OFF; Sale Price Tk 10,00,00,000 accepted; Discount -1 % accepted | `/sale`, TEST PRODUCT, Retail |
| OBS-SALE-010 | Info | Loss-sale block says only "Selling TEST PRODUCT below cost is not allowed for this pharmacy" and the POS shows "Last Purchase Tk 3.32" while the FEFO batch cost is Tk 7.32/pc, so a Tk 6.00 price (above the shown cost) is rejected at checkout without explaining why | TC-SALE-SC-13 |
| OBS-SALE-011 | Info | Opening Cash Closer shows "Last saved by Training Client 1:04:28 PM" without pressing Save Closing (page appears to auto-save on load) | `/accounts/cash-closer` |
| OBS-SALE-012 | Info | Dashboard "Payment Method Mix" stays 30/30/30/10 (it mirrors treasury balances) although all of today's sales were cash | Label suggests sale mix |
| BUG-SALE-017 | Medium | **Checkout shows an existing Due as an Advance balance**: Manik Hossain (Due Tk 25) appears as "Previous Balance (Adv.) Tk 25", paying Tk 80 on Tk 50 previews "New Balance (Adv.) Tk 55" and the Excess dialog says "Current Due: Tk 0.00"; the saved result is correct (Advance Tk 5) | observed 2026-10-27 (screenshot not kept) |
| BUG-SALE-018 | Medium | **Sale Record search does not match invoice numbers**: SALE_20261027_02 / 20261027_02 / walk-in return nothing; "_02" returns #06 and #04 | Searched on /sale-record, 7 rows |
| BUG-SALE-019 | Medium | **Return screen opens for a cancelled sale** (no block, no message); completing was not attempted | `/sale-return?saleId=59` |
| BUG-SALE-020 | Low | **Return Qty accepts 0, -1, 0.5, text and qty above sold with no message** (refund silently capped) | Return on #SALE_20261027_04 |
| OBS-SALE-013 | Info | Sale Record Status filter offers Paid / Due / Cancelled / Returned but no "Advance", although sales #03 and #06 have status Advance; Sold By filter lists no users | Filters on /sale-record |
| OBS-SALE-014 | Info | Sale Record tiles never change when filters are applied (always the whole period); table headers have no sort controls | Status / Payment filters |
| OBS-SALE-015 | Info | After a partial return the sale row's status cell is blank (sale #02); the return row shows Profit Tk -32.68 | Sale Record |
| OBS-SALE-016 | Info | Customer discount 101 % was saved as 100 % with no message; add-customer phone letters are stripped silently | Add New Customer |
| BUG-SALE-021 | Medium | **Separate Cashier ON: a sale still waiting in the cashier queue is already "Paid" and counted as collected in Sale Record** (toast says completed; Sale Record Paid Tk 100, profit 85.36, Total Collected 629) | #SALE_20261027_10; SRS: pending, no ledger/treasury effect until approval |
| OBS-SALE-017 | Info | Out of Stock Sale ON: selling a 0-stock product works (stock -2) but cost and profit are "Pending" in Sale Details, the checkout shows "Approximate Profit: Pending" and the Sale Record tile reads "Tk 457 + pending"; no last-purchase fallback cost is applied | #SALE_20261027_08 |
| BUG-SALE-022 | High | **Double-click on Complete Sale creates two sales** (#SALE_20261027_12 and _13, both Tk 50 from one 1-pc cart) | Stock and cash taken twice |
| BUG-SALE-023 | High | **Allow Loss Sale OFF is bypassed by a line discount**: Tk 10 less 40 % (net 6 < cost 7.32) completed as #SALE_20261027_15 with profit Tk -2.64, while a plain 7.31 is blocked | 7.32 allowed, 7.31 blocked |
| BUG-SALE-024 | Low | **Checkout accepts invalid Paid / Discount silently**: -5 ignored, 12.345 shows Paid 12.35 + Due 87.66, 1e9 accepted, Tk 101 discount on Tk 100 shown with Final Tk 0 | Not submitted |
| OBS-SALE-018 | Info | The Cashier page keeps showing the approved sale's details after the queue becomes empty ("Queue is Empty" with the old panel); Rack No column appears in the cart only when Rack Number is ON | /cashier, /sale || BUG-SALE-025 | Medium | **Loyalty Config: negative numbers are saved as 0 with a success message; text shows 'Earning Rule is required'** | TC-SALE-LC-04 |
| BUG-SALE-026 | Medium | **Sale Return: after a full return of a loyalty sale the customer's Total Spent / Orders are unchanged and redeemed points are not restored** | TC-SALE-LY-10, TC-SALE-CU-24 |
| BUG-SALE-027 | Low | **Add Customer drawer keeps the previous values after Cancel and reopen** | TC-SALE-CU-12 |
| BUG-SALE-028 | Medium | **Customer Bad Debts write-off is accepted without a reason and asks for a payment method** | TC-SALE-CU-22 |
| BUG-SALE-029 | Low | **Sale Checkout: the customer's default discount % is not applied** | TC-SALE-CK-22 |
| BUG-SALE-030 | High | **POS sells an expired batch without any warning or block** | TC-SALE-PC-22, TC-SALE-IV-11 |
| BUG-SALE-031 | Low | **Sale Config: double-clicking Save Changes sends two updates and shows two toasts** | TC-SALE-SC-05 |
| BUG-SALE-032 | Low | **POS is unusable at phone width (390 px): text wraps one letter per line and the cart is crushed** | TC-SALE-PC-24 |
| BUG-SALE-033 | Low | **POS controls without accessible names (segmented radios, unit select)** | TC-SALE-NF-11 |
| BUG-SALE-034 | High | **Cashier queue: a discount typed by the cashier is ignored when the sale is approved** | TC-SALE-CA-03 |
| BUG-SALE-035 | Low | **POS cart: adding the same product twice silently replaces the first line** | TC-SALE-PC-14 |
| BUG-SALE-036 | Low | **Add Customer: a Due Payment Date in the past is accepted without a warning** | TC-SALE-CU-11 |
| OBS-SALE-019 | Info | Customer List tiles (Due / Active) do not refresh after adding a customer until the page is reloaded | /customer |
| OBS-SALE-020 | Info | The POS remembers the last payment method: after one CARD split test every later sale defaulted to CARD | Sale Record shows CARD for cash-intended sales |
| OBS-SALE-021 | Info | Pending cashier sales deduct stock immediately (108,110 -> 108,108 after a 2-pc pending sale) | CA-07 |
| OBS-SALE-022 | Info | Double-click on Complete Sale Return sends 2 requests; the second is rejected ("exceeds the remaining 0") and an error toast appears although the return was created | Return #20 |
| OBS-SALE-023 | Info | Dashboard sidebar badge shows Due Collect 1 for an overdue customer due, but BUG-SALE-012 (no date) customers are still missing from it | Due Collect || BUG-SALE-037 | Medium | **Checkout: the overall discount is also applied to line-discounted items** | TC-SALE-CK-06, TC-SALE-IV-10 |
| BUG-SALE-038 | Low | **Sale Return: each single-piece return is rounded up, so returning piece by piece refunds more than the line total** | TC-SALE-NF-05, TC-SALE-RT-08 |
| BUG-SALE-039 | Medium | **Cancel Sale is allowed on a sale that already has a return (no warning), while Edit Sale says 'not editable'** | TC-SALE-SR-11 |
| BUG-SALE-040 | High | **API accepts a walk-in sale with a shortfall as Due (settlement choice bypassed) - walk-in customers can end up with a Due** | TC-SALE-NF-03 |
| BUG-SALE-041 | Low | **Negative-stock sale shows cost and profit as 'Pending' instead of the last-purchase fallback cost** | TC-SALE-IV-06 |
| BUG-SALE-042 | withdrawn | **Withdrawn - tester error**: Sale Edit History does list before/after values; the entry has to be expanded (click 'Edit') to show the Field Name / From / To table | Verified 2026-10-28 on sale #24 |
| OBS-SALE-024 | Info | Sale Details has a "Print Receipt" button (80 mm PDF); Edit History shows "Cash Received" as the first change of every sale | Sale Details |
| OBS-SALE-025 | Info | The Edit Sale screen resets Total Paid to the old paid amount (a Tk 71 edit shows Paid Tk 144) and then always opens the Excess Payment dialog | /sale/edit/checkout |
| BUG-SALE-046 | Low | **Rack Number ON: the rack is shown in the cart but not in the search dropdown** | TC-SALE-SC-29 |
| BUG-SALE-047 | Medium | **Sale Record applies a hidden default 'today' date filter: the grid is empty while the tiles show every sale** | TC-SALE-SR-01, TC-SALE-SR-02, TC-SALE-SR-04 |
| BUG-SALE-048 | Medium | **Sale Record: the Status filter returns no rows for Paid or Due** | TC-SALE-SR-04 |
| BUG-SALE-049 | Low | **Pay Due records the payment but offers no payment voucher to print** | TC-SALE-SR-18 |
| BUG-SALE-050 | Low | **Cashier approval does not generate a receipt** | TC-SALE-CA-13 |
| OBS-SALE-026 | Info | Refunds for a registered customer settle against the balance automatically (Due 400 -> 350, Advance 5 -> 199) and no refund-method choice is offered; Total Spent / Orders are still not reduced (BUG-SALE-026) | Return Checkout |
| OBS-SALE-027 | Info | Pay Due is disabled for a walk-in sale that carries a Due (the Due created through BUG-SALE-040 cannot be collected) | #SALE_20261027_30 |
| BUG-SALE-051 | Low | **Add Customer: phone digits beyond the 10th are silently dropped and the shortened number is saved** | TC-SALE-CU-06 |
| BUG-SALE-052 | Low | **Add Customer: the name is saved with its leading and trailing spaces** | TC-SALE-CU-08 |
| BUG-SALE-053 | Low | **Opening balance is rounded to a whole taka, has no upper limit, and a negative value silently becomes 0** | TC-SALE-CU-10 |
| BUG-SALE-054 | Low | **The checkout Note and Walk in Customer Detail are not shown anywhere on the saved sale** | TC-SALE-CK-30, TC-SALE-CK-19 |
| BUG-SALE-055 | High | **Double-clicking Confirm New Payment records the customer payment twice** | TC-SALE-CU-18, TC-SALE-SR-09 |
| BUG-SALE-056 | Low | **Double-clicking Hold Current Sale creates two holds** | TC-SALE-HS-02 |
| OBS-SALE-028 | Info | Edge sweep: Add to Cart double-click adds one line; the Note stops at 150 characters; a name of 255 characters is accepted and 256 rejected; Back after a completed sale shows an empty checkout; double-click Cancel Sale sends one request | 2026-10-28 |
| OBS-SALE-029 | Info | Customer balances are stored with a sign (Advance negative, Due positive) and the discount box silently clamps to 0-100 | create payloads |
| BUG-SALE-057 | Low | **Double-clicking Confirm New Customer or Complete Sale Return sends two requests; the second is rejected and an error toast hides the success** | TC-SALE-CU-13, TC-SALE-RT-16 |
| BUG-SALE-058 | Low | **Loyalty Config: Redemption Rule 0 is saved with a success message although a zero redemption rule is not allowed** | TC-SALE-LC-03 |
| BUG-SALE-059 | Medium | **Return Checkout gives a registered customer no refund-method choice (Cash or reduce balance); the refund is always settled against the balance** | TC-SALE-RT-17 |
| BUG-SALE-060 | Medium | **The Cashier queue has no Reject / Cancel action for a pending sale** | TC-SALE-CA-06 |
| BUG-SALE-043 | Medium | **Profit is shown in the Cashier panel and in Sale Record although Profit Margin is OFF** | TC-SALE-SC-28 |
| BUG-SALE-044 | Low | **Checkout summary has no line-discount row, so Gross - Discounts does not add up to Final Price** | TC-SALE-CK-31 |
| BUG-SALE-045 | Low | **Cashier panel cannot change quantities of a queued sale** | TC-SALE-CA-12 |

Registered-customer checkout (Manik Hossain, 100 pcs NAPA 500 = Tk 120, **sale not completed**): previous balance Adv Tk 0; paid 150 -> New Balance Adv Tk 30; paid 100 -> New Balance Due Tk 20; paid 0 -> Due Tk 120 and Complete Sale still enabled; 10 % discount -> Tk 12.00 off, final Tk 108.

Behaviour confirmed **as specified**: Profit Margin OFF -> no profit on checkout; Rack Number OFF -> no rack shown; Separate Cashier OFF -> checkout offers direct *Complete Sale*; unit toggle Pcs/Box; price auto-fills (Sale/pc 1.20, Sale/bx 612.00 = 1.20 x 510); cart survives reload; Quick Print is unchecked by default; registered-customer checkout preview is correct (see below).

## 4. Requirement questions and the product owner's answers

All 10 questions were answered by the product owner (2026-10-29). The answers are the expected behaviour used by the cases in section 5.

| # | Question | Answer | Effect on the cases |
|---|---|---|---|
| 1 | Round Off method and sign | Nearest whole taka (145.35 -> 145, 161.50 -> 162, 2.40 -> 2) | CK-07 / CK-08 confirmed (Pass) |
| 2 | Overall discount and line-discounted items | A product that already has a line discount gets **no** overall discount, flat or percentage; the other products do get it | BUG-SALE-037 confirmed (CK-06, IV-10); applies to flat Tk as well |
| 3 | Discount limits | Percentage must be below 100 % (100 % not allowed); a flat discount must be below the bill amount; negative not allowed; Final Price never negative | BUG-SALE-024 confirmed (CK-05); "= total" and "100 %" are also invalid |
| 4 | Loyalty with zero rules | Earning 0 is accepted; Redemption 0 (or below the minimum redemption) is not allowed and Apply Loyalty Points must be disabled | LC-03 now Fail (BUG-SALE-058); Apply-disabled state not yet verified at POS |
| 5 | Hold Sale | A held cart does not reserve stock (the stock figure is unchanged) | HS-05 is now executable (hold, sell the stock elsewhere, resume); hold expiry and who may resume were not answered |
| 6 | Cancel Sale | Not allowed after a return of that sale (cancel the return first); no reason required | BUG-SALE-039 confirmed (SR-11); after Cash Closer still unanswered (SR-13) |
| 7 | Returns | No time window; a registered customer's refund is paid in cash or adjusted against their balance, the seller's choice; a walk-in refund is cash; stock and stock value rise, cash falls | BUG-SALE-009 confirmed (RT-12, RT-13); RT-17 now Fail (BUG-SALE-059: no choice is offered) |
| 8 | Phone and name | A walk-in and a registered customer may share a number; Bangladesh only, 10 digits after a fixed +880; name up to 255 characters | CU-06 / CU-08 expectations confirmed; 256 characters is rejected (guard passes) |
| 9 | Cashier approval | The salesperson can edit or cancel a pending sale; pending sales deduct stock immediately; the queue should offer reject / cancel; if stock runs out the seller reduces the quantity, sells (negative sale allowed) or cancels | OBS-SALE-021 is by design; CA-07 Pass; CA-06 now Fail (BUG-SALE-060) |
| 10 | Wholesale mode | Wholesale only switches to Box and uses the wholesale selling and purchase price per box / piece; no tiers, no minimum quantity | PC-25 confirmed (Pass); PC-20 (BUG-SALE-014) unchanged |

Still open (not asked or not answered): hold expiry and who may resume a hold (HS-10), cancel after Cash Closer (SR-13), points on a partly paid or due sale (LY-09), refund tender for Card / MFS sales.

## 5. Test cases

Pre-conditions common to all: Owner logged in to Manik Pharma; unique test data (`QA-SALE-<timestamp>`). "Cfg" = Sale Config toggle states; restore all to OFF/Retail after each config test.

### 5.1 Sale Config (SC) - settings and their effect on POS

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-SC-01 | Page loads with persisted values | Open Settings > Sale Config | 7 toggles + Business Type shown; states match `GET sales-configs/{id}`; Save/Cancel visible | P1 | Pass (all OFF, Retail) |
| TC-SALE-SC-02 | Save each toggle persists | Turn one toggle ON, Save, reload | Toggle stays ON; API value true; other toggles unchanged (x7) | P1 | Pass (6 toggles + Separate Cashier saved and persisted after reload; others not run individually) |
| TC-SALE-SC-03 | Cancel discards | Change toggles, click Cancel, reload | Original values remain, no API write | P2 | Pass |
| TC-SALE-SC-04 | Leave page unsaved | Toggle, navigate away | No change saved (or unsaved-changes warning - ask) | P3 | Pass (unsaved change discarded silently, no warning) |
| TC-SALE-SC-05 | Double-click Save | Click Save twice quickly | One request / one success toast (cf. BUG-INV-056 on Inventory Config) | P3 | **Fail** BUG-SALE-031 |
| TC-SALE-SC-06 | Settings apply without re-login | Change toggle, open /sale in same session | New behaviour visible immediately | P1 | Pass |
| TC-SALE-SC-07 | Per-pharmacy scope | Change config in Manik Pharma, switch to QA Ret Pharma A | Other pharmacy unaffected | P1 | Pass (customers and loyalty config are per pharmacy) |
| TC-SALE-SC-08 | Business Type Retail -> Wholesale | Switch, Save | POS default mode/unit follows type (Wholesale -> Box); see 5.4 | P2 | Pass (Wholesale: POS default unit Box) |
| TC-SALE-SC-09 | Non-owner access | Log in as staff without settings permission; open `/settings/sale-config` directly | Access denied / redirected; API write rejected 403 | P1 | Blocked (needs a non-owner login) |
| TC-SALE-SC-10 | Out of Stock Sale OFF hides 0/negative-stock products | Cfg OFF; search a product with 0 stock | Product not in dropdown | P1 | **Fail** BUG-SALE-001 |
| TC-SALE-SC-11 | Out of Stock Sale OFF blocks adding | Cfg OFF; add product with stock 3, qty 5 | Blocked with message "exceeds available stock" | P1 | **Fail** BUG-SALE-001 |
| TC-SALE-SC-12 | Out of Stock Sale ON allows and goes negative | Cfg ON; sell 5 of a 0-stock product; complete | Sale completes; stock = -5; COGS uses last-purchase fallback (5.7) | P1 | Pass (cost/profit shown as Pending - OBS-SALE-017) |
| TC-SALE-SC-13 | Allow Loss Sale OFF blocks | Cfg OFF; price below last purchase (1.06) e.g. 0.90; Complete | Warning/blocked, no sale created, audit entry optional | P1 | Pass |
| TC-SALE-SC-14 | Allow Loss Sale OFF boundary | price = cost (1.06), cost+0.01, cost-0.01 | = cost and above allowed; below blocked | P1 | Pass (7.32 allowed, 7.31 blocked) |
| TC-SALE-SC-15 | Allow Loss Sale ON allows | Cfg ON; same price | Sale completes; profit negative; audit log entry for loss sale | P1 | Pass |
| TC-SALE-SC-16 | Loss caused by discount | OFF; price 1.20, discount makes net < cost | Same block as SC-13 (net price vs cost) | P1 | **Fail** BUG-SALE-023 |
| TC-SALE-SC-17 | Stock Qty OFF hides stock | Cfg OFF; search + cart | No stock figures anywhere | P2 | **Fail** BUG-SALE-002 |
| TC-SALE-SC-18 | Stock Qty ON shows stock | Cfg ON | Pcs and box stock in dropdown and cart row | P2 | Pass (shown, but also shown when OFF: BUG-SALE-002) |
| TC-SALE-SC-19 | Company Name OFF hides company | Cfg OFF | No company in dropdown/cart | P3 | **Fail** BUG-SALE-003 |
| TC-SALE-SC-20 | Company Name ON shows company | Cfg ON | Company in dropdown and cart | P3 | Pass (shown, but also shown when OFF: BUG-SALE-003) |
| TC-SALE-SC-21 | Profit Margin OFF hides profit | Cfg OFF; open checkout | No profit/margin | P2 | Pass |
| TC-SALE-SC-22 | Profit Margin ON shows profit | Cfg ON; checkout | Estimated profit and margin visible and = (sale - batch cost) | P2 | Pass |
| TC-SALE-SC-23 | Rack OFF/ON | Toggle; search/cart | OFF hidden (Pass); ON shows rack no. of the product | P3 | Pass |
| TC-SALE-SC-24 | Separate Cashier OFF | Checkout > Complete Sale | Sale completes immediately; stock deducted, ledger posted | P1 | Pass |
| TC-SALE-SC-25 | Separate Cashier ON | Complete Sale | Status "Pending Cashier Approval"; no ledger/treasury entry; stock already deducted (answer 9) | P1 | **Fail** BUG-SALE-021 |
| TC-SALE-SC-26 | Toggle combinations (pairwise) | e.g. OOS ON + Stock Qty ON; Loss ON + Profit ON; Cashier ON + Profit ON | Each rule independent, no UI crash | P2 | Pass (six toggles ON together; no crash) |
| TC-SALE-SC-27 | Config change with items in cart/held | Items in cart, change OOS to OFF, resume | Defined behaviour (revalidate at checkout) | P2 | Blocked (gap) |
| TC-SALE-SC-28 | Profit Margin OFF hides profit in the cashier and sales views (SRS 2.1.5) | Profit Margin OFF; open Cashier with a queued sale and Sale Record | No profit figures on checkout, Cashier panel, Sale Record grid or tiles | P2 | **Fail** BUG-SALE-043 |
| TC-SALE-SC-29 | Rack Number ON shows the rack in the search dropdown and the cart (SRS 2.1.6) | Rack ON; search a product that has a rack no. (TEST PRODUCT, rack A1); add to cart | Rack A1 in the dropdown option and a Rack No column in the cart | P3 | **Fail** BUG-SALE-046 |

### 5.2 Loyalty Config (LC)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-LC-01 | Defaults | Open Loyalty Config | Fields: Earning (Tk per 1 pt), Redemption (points per 1 Tk), Min redeem, Max redeem per txn; current values all 0 | P2 | Pass |
| TC-SALE-LC-02 | Save valid values | 100 / 10 / 50 / 500; Save; reload | Persisted | P1 | Pass |
| TC-SALE-LC-03 | Zero values | Earning 0 or Redemption 0 | Earning 0 accepted; Redemption 0 (or below the minimum) rejected and Apply Loyalty Points disabled (answer 4) | P1 | **Fail** BUG-SALE-058 |
| TC-SALE-LC-04 | Invalid values | negative, decimal, text, 1e9, empty, leading/trailing spaces | Rejected with message or sanitised; never saved as NaN | P2 | **Fail** BUG-SALE-025 |
| TC-SALE-LC-05 | Min > Max | Min 600, Max 500 | Validation error | P2 | Pass (server: Minimum redeem point must not be greater than maximum) |
| TC-SALE-LC-06 | Cancel / reload | Edit, Cancel | Reverts | P3 | Pass |
| TC-SALE-LC-07 | Permission | Non-owner direct URL | Denied | P2 | Blocked (needs a non-owner login) |

### 5.3 Customer management (CU)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-CU-01 | List & tiles on empty pharmacy | Open /customer | Tiles 0, "No customers found", tabs All/Due/Advance/Loyalty 0 | P3 | Pass |
| TC-SALE-CU-02 | Add form layout | Click Add New Customer | Drawer with fields in 3 (Name\*, Phone\* mandatory), Active default, Loyalty Inactive | P2 | Pass |
| TC-SALE-CU-03 | Create minimum customer | Name + phone only; Confirm | Created; appears in list; balance 0; loyalty inactive | P1 | Pass |
| TC-SALE-CU-04 | Create full customer | All fields incl. Due opening balance 500, discount 5 %, due date | Saved; Due tab count +1; balance "Due 500"; due appears in Due Collect on its date | P1 | Pass |
| TC-SALE-CU-05 | Required fields | Empty name; empty phone; both | Inline errors; no request | P1 | Pass |
| TC-SALE-CU-06 | Phone validation | 9, 10, 11 digits, letters, +880 twice, leading 0, spaces | Bangladesh numbers only: 10 digits after a fixed +880; a walk-in and a registered customer may share one (answer 8) | P1 | **Fail** BUG-SALE-051 |
| TC-SALE-CU-07 | Duplicate phone | Create twice with same phone | Second rejected "phone already exists" | P1 | Pass (also with leading 0) |
| TC-SALE-CU-08 | Name boundaries | 1 char, 100, 256, emoji, Bangla, `<script>`, spaces only, leading/trailing spaces | 255 characters accepted, 256 rejected; trimmed; XSS escaped; spaces-only rejected (answer 8) | P2 | **Fail** BUG-SALE-052 |
| TC-SALE-CU-09 | Discount % boundaries | -1, 0, 0.01, 100, 100.01, text | 0-100 only | P2 | Pass (-1 / text become 0, 100.01 becomes 100, 0.01 and 100 kept; no messages) |
| TC-SALE-CU-10 | Opening balance Advance/Due | Both types, 0, negative, decimals | Correct sign in list; negative rejected | P1 | **Fail** BUG-SALE-053 |
| TC-SALE-CU-11 | Due date | Past date, today, future, with no Due balance | Past rejected or flagged; field only relevant with Due | P2 | **Fail** BUG-SALE-036 |
| TC-SALE-CU-12 | Cancel/close drawer | Fill, Cancel / X / Esc | Nothing saved, no leak into next open | P3 | **Fail** BUG-SALE-027 |
| TC-SALE-CU-13 | Double-click Confirm | Rapid double click | One customer | P2 | **Fail** BUG-SALE-057 |
| TC-SALE-CU-14 | Search | name part, phone part, case, no result, special chars, spaces | Correct list | P2 | **Fail** BUG-SALE-013 |
| TC-SALE-CU-15 | Filters | Status, Channel, tabs (Due/Advance/Loyalty), combined, Reset | Counts equal tab badges | P2 | Pass (Due tab not run) |
| TC-SALE-CU-16 | Paging | 10/20/50 per page, next/prev, Go to | Consistent rows | P3 | Pass |
| TC-SALE-CU-17 | Edit customer | Change name, discount, status Inactive | Persisted; Inactive hidden from POS search (confirm) | P1 | Pass |
| TC-SALE-CU-18 | Add Payment (collect due) | Customer with Due 500; pay 200, 500, 600 | Due 300 / 0 / overpay -> Advance 100 (or blocked - gap); treasury + payment history updated | P1 | **Fail** BUG-SALE-055 |
| TC-SALE-CU-19 | Add Payment (advance deposit) | Deposit 1000 | Advance 1000; ledger line | P1 | Pass |
| TC-SALE-CU-20 | Customer Ledger | After sale, collection, return | Chronological, running balance correct, totals agree with list | P1 | **Fail** BUG-SALE-007 |
| TC-SALE-CU-21 | Payment History by tender | Cash + Card + MFS payments | Grouped by tender, totals match | P2 | Pass (empty state; Add New Payment present) |
| TC-SALE-CU-22 | Bad Debt Write-off | Due 500; write off without reason; with reason | Reason mandatory (supervisor); balance 0; audit entry; treasury unchanged | P1 | **Fail** BUG-SALE-028 |
| TC-SALE-CU-23 | Loyalty member activation | Toggle Loyalty ON | OTP SMS to phone; 3-min expiry; wrong OTP rejected; accrual starts only after verification | P1 | Blocked (the only loyalty customer was activated earlier; enabling it on another customer would SMS a phone number the tester does not own) |
| TC-SALE-CU-24 | Total Orders / Total Spent | After 2 sales and 1 return | Orders 2; Spent = net of return | P1 | **Fail** BUG-SALE-026 |
| TC-SALE-CU-25 | Delete/deactivate with history | Customer with sales | Cannot hard-delete; deactivate keeps history | P2 | Pass (no delete action in the menu; Edit > Inactive deactivates) |
| TC-SALE-CU-26 | View Details shows the selected customer's own data | Row menu > View Details for Manik Hossain (list: 0 pts, 0 orders, Tk 0) | Drawer shows Manik Hossain, +8801521503629, balance Tk 0, discount 0 %, 0 points, 0 orders, no recent orders | P1 | **Fail** BUG-SALE-006 |
| TC-SALE-CU-27 | Row action menu | Open Actions on a customer | View Details, Customer Ledger, Payment History, Edit; Add Payment reachable under Payment History > Add New Payment; Payment Type offers Payment / Return / Bad Debts (write-off entry) | P2 | Pass |
| TC-SALE-CU-28 | Customer list API vs UI | Compare `GET customers/{pharmacy}` with row | name, phone, points, orders, spent, balance, status equal | P2 | Pass |

### 5.4 POS - product search and cart (PC)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-PC-01 | Initial state | Open /sale | Empty cart "Cart is empty", Retail mode, Hold List 0, Hold/Checkout disabled, Total Tk 0.00 | P2 | Pass |
| TC-SALE-PC-02 | Search by brand | "napa" | Matching brand/strength/form/generic/company results | P1 | Pass |
| TC-SALE-PC-03 | Search by generic | "paracetamol" | Products of that generic | P1 | Pass (generic and dosage-form search) |
| TC-SALE-PC-04 | Search variants | uppercase/lowercase, partial, leading/trailing space, `%`, `'`, `<b>`, Bangla, 1 char, 200 chars | No crash (cf. catalog `%` crash), sensible results, empty state "No data" | P1 | Pass (see remark: % acts as a wildcard) |
| TC-SALE-PC-05 | Select product auto-fill | Select NAPA 500 MG | Sale price/pc 1.20, Qty/Box 510, last purchase 1.06 shown, price field filled | P1 | Pass |
| TC-SALE-PC-06 | Add valid line | Qty 5 pcs | Row: qty 5 pc, Sale/pc 1.20, Sale/bx 612.00, price 6.00, total 6.00, count 1 | P1 | Pass |
| TC-SALE-PC-07 | Required validation | Add with no product / no qty / no price | Inline required errors; nothing added | P1 | Pass |
| TC-SALE-PC-08 | Qty boundaries | 0, -1, 0.5, 1, 2.5 (pieces), 999999, 1e3, text | Integer >= 1 for pcs; decimals handled (cf. 2.5 pc crash in returns) | P1 | **Fail** BUG-SALE-016 |
| TC-SALE-PC-09 | Unit conversion | Switch Pcs -> Box | Price/box = price/pc x Pcs-per-box (1.20 x 510 = 612); qty in boxes deducts boxes x 510 pieces | P1 | Pass (1 box = 10 pcs, see IV-04) |
| TC-SALE-PC-10 | Price boundaries | 0, -1, 0.001, 3 decimals, huge | 0 rejected/flagged; max 2 dp; no negative | P1 | Pass |
| TC-SALE-PC-11 | Line discount % | 10 % on 6.00 | Line total 5.40 | P1 | Pass |
| TC-SALE-PC-12 | Line discount Tk | 1.00 on 6.00 | 5.00 | P1 | Pass |
| TC-SALE-PC-13 | Discount boundaries | 0, 100 %, 100.01 %, Tk > line total, negative, switch % <-> Tk with value present | > 100 % / > total blocked; unit switch recalculates or clears | P1 | **Fail** BUG-SALE-016 |
| TC-SALE-PC-14 | Same product twice | Add NAPA 500 twice | Merged or two lines (record behaviour; totals correct either way) | P2 | **Fail** BUG-SALE-035 |
| TC-SALE-PC-15 | Edit cart line | Pencil -> change qty/price/discount | Row and total update; validation re-applied | P1 | Pass |
| TC-SALE-PC-16 | Delete cart line | Trash | Removed, total recalculated; no confirmation (OBS-SALE-007) | P2 | Pass |
| TC-SALE-PC-17 | Multi-line totals | 3 products, mixed discounts | Total = sum of line totals; item count correct | P1 | Pass |
| TC-SALE-PC-18 | Cart persistence | Add item, reload / navigate away and back | Cart retained (observed) - and cleared after Complete Sale | P2 | Pass (retained) |
| TC-SALE-PC-19 | Two tabs | Same cart in two tabs, complete in one | Other tab cannot double-sell; stale cart handled | P2 | Pass (server-side cart; the other tab shows it after reload) |
| TC-SALE-PC-20 | Retail vs Wholesale mode | Toggle Wholesale | Wholesale switches to Box and the wholesale price; no tier or minimum (answer 10); cart prices recalc or mode locked while the cart is non-empty (record) | P1 | **Fail** BUG-SALE-014 |
| TC-SALE-PC-21 | Product without price / expiry / batch | Product with no sale price | Price required; no crash; expiry shows "-" not 1970 | P2 | Blocked (every sampled product has a sale price; no price-less / batch-less product available) |
| TC-SALE-PC-22 | Expired batch | Product whose only batch is expired | Not sellable or warned (confirm) | P1 | **Fail** BUG-SALE-030 |
| TC-SALE-PC-23 | Keyboard | Enter in search/qty adds line; Tab order | Works without mouse | P3 | Pass (logical tab order) |
| TC-SALE-PC-24 | Responsive | 1366, 1024, 768 widths | No overflow; table scrolls | P3 | **Fail** BUG-SALE-032 |
| TC-SALE-PC-25 | Wholesale mode uses the wholesale price schedule (SRS 4.1) | Business Type Wholesale; select a product with retail 6 / wholesale 5 per pc | Default unit Box; price auto-fills from the wholesale price (50 per box), not retail (60) | P2 | Pass (Wholesale: default unit Box, wholesale price 50 per box, not retail 60) |
| TC-SALE-PC-26 | Price per Box = price per pc x pcs per box (SRS 4.2.2) | TEST PRODUCT (10 pcs/box): switch Pcs <-> Box with the default and a typed price | Default box price 60 for 6 per pc; typed 50 per pc shows Sale/bx 500 | P2 | Pass (default 6 -> 60 per box; 50 per pc shows Sale/bx Tk 500.00) |

### 5.5 Hold sale (HS)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-HS-01 | Hold with note | Cart with 2 items; Hold Current Sale; note | Cart cleared; Hold List badge 1; note + timestamp listed | P1 | Blocked (gap: no note prompt on Hold) |
| TC-SALE-HS-02 | Hold without note | Hold, no note | Allowed (note optional) | P2 | **Fail** BUG-SALE-056 |
| TC-SALE-HS-03 | Resume held sale | Open Hold List, resume | Items, qty, prices, discounts restored exactly; entry removed from list | P1 | Pass |
| TC-SALE-HS-04 | Process another sale while held | Hold A, sell B, resume A | Both correct | P1 | Pass |
| TC-SALE-HS-05 | Held sale and stock | Hold qty = whole stock, sell the stock elsewhere, resume | Stock revalidated at resume/checkout | P1 | Blocked (answer 5: a hold does not reserve stock; now executable, not yet run) |
| TC-SALE-HS-06 | Delete held sale | Delete from list | Gone; confirmation shown | P2 | Pass |
| TC-SALE-HS-07 | Multiple holds | Hold 3 | Count 3; each resumable independently | P2 | Pass (2 holds) |
| TC-SALE-HS-08 | Hold from checkout screen | "Hold Current Sale" on checkout | Same as HS-01, customer/discount state retained | P2 | Pass (overall discount kept after Hold from checkout and Resume) |
| TC-SALE-HS-09 | Hold with empty cart | Button state | Disabled | P2 | Pass |
| TC-SALE-HS-10 | Held by user A seen by user B | Two users | Per rules (confirm) | P3 | Blocked (gap) |

### 5.6 Checkout, payment and settlement (CK)

Test data: NAPA 500 MG 1.20/pc, cost 1.06. For clean arithmetic use qty so Gross = 100 etc. (e.g. a product priced 100).

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-CK-01 | Checkout summary | Go to Sale Checkout | Items, Total, Discount, Round Off, Final Price, Total Paid, Due shown; Paid pre-filled = Final | P1 | Pass |
| TC-SALE-CK-02 | Complete walk-in, exact pay | Paid = Final | Completed Sale; Sale Record row; stock down; Treasury +Final; Dashboard updated | P1 | Pass |
| TC-SALE-CK-03 | Overall discount % | 10 % on 500 | Final 450 | P1 | Pass |
| TC-SALE-CK-04 | Overall discount Tk | 50 | Final 450 | P1 | Pass |
| TC-SALE-CK-05 | Discount boundaries | 0, = total, > total, >100 %, negative, text | Percentage below 100 % and flat below the bill total; 100 %, = total, negative and text blocked; Final Price never negative (answer 3) | P1 | **Fail** BUG-SALE-024 |
| TC-SALE-CK-06 | Line-discounted items excluded from overall discount | Item A line-disc 10 %, Item B none; overall 10 % | An item with a line discount gets no overall discount (% or flat); the other items do (answer 2) | P1 | **Fail** BUG-SALE-037 |
| TC-SALE-CK-07 | Round-off | Gross 99.60 / 99.40 / 100.50 | Final whole integer; Round Off line shows signed delta (method per gap 1) | P1 | Pass (nearest whole taka, confirmed by answer 1: 145.35 -> 145, 161.50 -> 162) |
| TC-SALE-CK-08 | Final price formula | Gross 500, line disc 20, overall 30, loyalty 10, round | Final = 500-20-30-10 +/- round (5.7 oracle) | P1 | Pass (161.50 - 16.15 overall 10 % = 145.35, round -0.35, final 145) |
| TC-SALE-CK-09 | Walk-in underpay -> Less & Sale | Final 450, paid 400 | Status Less & Sale; no due; deficit 50 reduces profit by 50 distributed across lines | P1 | Pass |
| TC-SALE-CK-10 | Walk-in overpay -> Profit & Sale | paid 500 | Profit & Sale; surplus 50 added to profit; no advance | P1 | **Fail** BUG-SALE-008 |
| TC-SALE-CK-11 | Registered underpay -> Due & Sale | Customer, paid 400 | Due 50 added to customer ledger; Sale status Due; appears in Due Collect; projected new balance preview correct before completing | P1 | Pass |
| TC-SALE-CK-12 | Registered overpay -> Advance & Sale | paid 500 | Advance 50 credited | P1 | Pass |
| TC-SALE-CK-13 | Registered with existing Due/Advance | Previous Due 100 then paid = Final | Balance unchanged (100); preview shows "Due 100" | P1 | **Fail** BUG-SALE-017 |
| TC-SALE-CK-14 | Paid = 0 | Registered / walk-in | Registered: full due; walk-in: full Less & Sale or blocked (gap) | P1 | Pass (walk-in paid 0 -> Less & Sale: Tk 0 bill with -Tk 50 disc, profit -7.15; no limit on a full waiver) |
| TC-SALE-CK-15 | Paid boundaries | negative, text, 1e9, decimals, blank | Rejected; 2 dp max | P1 | **Fail** BUG-SALE-024 |
| TC-SALE-CK-16 | Split payment | Cash 200 + Card 150 + MFS 100 | Sum = paid; each tender recorded in Payment History and Treasury accounts | P1 | Pass |
| TC-SALE-CK-17 | Card commission | Card payment with commission % | Commission recorded; not charged to customer unless specified (confirm) | P2 | Pass (2 % on the card portion is added to the final price: 145 -> 149; formula looks gross-up) |
| TC-SALE-CK-18 | Cash Received / change | Cash received 600, final 450 | Change 150 displayed; not stored as advance | P2 | Pass |
| TC-SALE-CK-19 | Walk-in detail | Name/phone optional; invalid phone | Optional; invalid phone rejected if entered | P2 | Pass (detail accepts 400 chars with no limit; HTML is inert; it is not shown afterwards: BUG-SALE-054) |
| TC-SALE-CK-20 | Walk-in cannot hold balance/loyalty | Walk-in: no Due/Advance; no loyalty section | As SRS 3.1 | P1 | **Fail** BUG-SALE-008 |
| TC-SALE-CK-21 | Registered customer picker | Choose Customer, search by name and phone | Metadata shown: previous balance Adv./Due, points, projected balance | P1 | Pass |
| TC-SALE-CK-22 | Default customer discount | Customer with 5 % | Auto-fills discount 5 %; editable | P1 | **Fail** BUG-SALE-029 |
| TC-SALE-CK-23 | Add New Customer from checkout | Create inline | Selected automatically; persisted | P2 | Pass |
| TC-SALE-CK-24 | Quick Print on/off | Complete with ON and OFF | ON: print dialog; OFF: completes silently | P3 | Pass (a print iframe is created; the printout itself is not checked) |
| TC-SALE-CK-25 | Double-click Complete Sale | Rapid double click | One sale only, one stock deduction | P1 | **Fail** BUG-SALE-022 |
| TC-SALE-CK-26 | Network failure during Complete | Offline / API 500 | Error shown; cart kept; no partial sale | P1 | Pass ('Network Error' toast, cart kept, button re-enabled) |
| TC-SALE-CK-27 | Back/refresh on checkout | Reload, browser Back | Cart/checkout state preserved or safely returned; no duplicate | P2 | Pass (reload keeps the cart; Back returns to /sale) |
| TC-SALE-CK-28 | Empty cart direct URL | `/sale-checkout` with empty cart | Redirect to /sale or message | P2 | Pass |
| TC-SALE-CK-29 | Customer Paid vs methods mismatch | Split sums != paid | Blocked / auto-adjusted | P1 | Pass (paid above the bill opens the Excess Payment dialog) |
| TC-SALE-CK-30 | Note | 0, 1, 500, 501 chars, special | Saved and shown on record | P3 | **Fail** BUG-SALE-054 |
| TC-SALE-CK-31 | Checkout summary shows the cumulative line discounts (SRS 4.3) | Cart with a 10 % line-discounted item; open checkout | A line-discount row so that Gross - Line - Overall - Loyalty +/- Round = Final is visible | P2 | **Fail** BUG-SALE-044 |
| TC-SALE-CK-32 | All four tenders can be used and are recorded (Cash, Bank Card, Bank transfer, MFS) | Pay one sale with each tender (and one split) | Each tender accepted; Treasury / Payment Method balance moves by that tender | P1 | Pass (CASH / BANK / CARD / MFS offered; CASH + CARD split completed; per-tender treasury not checked) |

### 5.7 Inventory deduction, COGS and profit (IV)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-IV-01 | Single batch deduction | Sell 5 from a batch of 100 | Batch 95; Product List stock 95; Inventory record batch 95 | P1 | Pass |
| TC-SALE-IV-02 | FEFO order | Batches B1 (exp earlier, 10), B2 (later, 50); sell 5 | B1 -> 5, B2 untouched | P1 | Pass (automated: 3BIOTIC 100GM, later-expiring batch bought first; selling 1 pc was costed at the earlier-expiry batch) |
| TC-SALE-IV-03 | Multi-batch spill | Sell 15 | B1 -> 0, B2 -> 45; Sale Details shows both batches with own cost | P1 | Pass (automated: selling 1 pc more than batch 1 held took it from batch 2; FEFO order kept) |
| TC-SALE-IV-04 | Box sale conversion | Sell 2 boxes, 510 pcs/box | 1020 pcs deducted | P1 | Pass (1 box = 10 pcs: stock 1,08,101 -> 1,08,091) |
| TC-SALE-IV-05 | COGS from batch | Batch cost 1.06 | Line profit = (1.20 - 1.06) x qty | P1 | Pass |
| TC-SALE-IV-06 | Fallback cost on negative stock | OOS ON; sell with no batch | Cost/pc = last purchase price per box / pcs per box | P1 | **Fail** BUG-SALE-041 |
| TC-SALE-IV-07 | Mixed batch + negative | Stock 3, sell 5 (OOS ON) | 3 from batch cost, 2 at fallback; stock -2 | P1 | **Fail** BUG-SALE-041 |
| TC-SALE-IV-08 | Proportional allocation | Items A 200, B 300; overall disc 50 | A net 180, B net 270; profit reduced 20 / 30 | P1 | Pass (return refunds follow the proportional split 81 / 63 of Tk 144) |
| TC-SALE-IV-09 | Allocation with Less/Profit & Sale + round-off | Walk-in paid 400 of 450 | Deficit spread by line weight; Sum of line profits = order profit | P1 | Pass (single line only) |
| TC-SALE-IV-10 | Loyalty/overall excluded items | One item line-discounted | Weight uses eligible subtotals only | P2 | **Fail** BUG-SALE-037 |
| TC-SALE-IV-11 | Expired batch skipped | Earlier batch expired | FEFO takes the active batch only | P1 | Blocked (gap) |
| TC-SALE-IV-12 | Concurrent sales | Two sessions sell the last 5 pcs simultaneously | One succeeds; other gets stock error (OOS OFF) or goes negative (ON); no double deduction | P1 | **Fail** BUG-SALE-022 |
| TC-SALE-IV-13 | Dependent modules agree | After sale compare Sale Record profit, Dashboard profit, Analytics, Product Movers, Cashbook | All equal | P1 | **Fail** BUG-SALE-008 |
| TC-SALE-IV-14 | Stock Adjust / purchase after sale | Add inventory, sell, adjust | Stock history shows sale line with invoice id | P2 | Blocked (needs Stock Adjust / purchase set-up in the Inventory module) |

### 5.8 Loyalty at POS (LY)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-LY-01 | Earn points | Earning 100 Tk = 1 pt; Registered loyalty member buys 1,050 | 10 points (floor); on which amount (final vs gross) - confirm | P1 | Pass |
| TC-SALE-LY-02 | Walk-in earns nothing | Walk-in buys | No points | P1 | Pass (no loyalty section for a walk-in) |
| TC-SALE-LY-03 | Non-activated customer | Loyalty member Inactive | No points | P1 | Pass (non-loyalty customer shows '-' points after a Tk 150 sale) |
| TC-SALE-LY-04 | Redeem with OTP | Min 50, rule 10 pts = 1 Tk; redeem 100 pts | OTP SMS, 3-min expiry; discount 10 Tk; points -100 | P1 | Pass |
| TC-SALE-LY-05 | OTP wrong / expired / resend | Wrong, wait 3 min, resend | Rejected; no discount applied | P1 | Pass (wrong code rejected; resend works; expiry not run) |
| TC-SALE-LY-06 | Below minimum | Balance < min | Redeem disabled with message | P1 | Pass (button hidden below the minimum) |
| TC-SALE-LY-07 | Above max per invoice | Request > max | Capped/blocked | P1 | Pass |
| TC-SALE-LY-08 | Redeem more than balance / more than bill | | Blocked | P1 | Blocked (only Apply Max is offered, so a manual over-redeem cannot be entered) |
| TC-SALE-LY-09 | Points on partially paid / due sale | Registered Due & Sale | Points rule per config (confirm) | P2 | Blocked (gap) |
| TC-SALE-LY-10 | Return after earn/redeem | Return item from loyalty sale | Points reversed / restored proportionally | P1 | **Fail** BUG-SALE-026 |
| TC-SALE-LY-11 | Audit | OTP redemption | Security log: staff id, time | P2 | Blocked (no audit view exposed in the UI) |

### 5.9 Cashier approval workflow (CA) - Separate Cashier ON

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-CA-01 | Submit to queue | Complete as salesperson | Status Pending Cashier Approval; Queue +1; no treasury/ledger entry; stock reserved only | P1 | **Fail** BUG-SALE-021 |
| TC-SALE-CA-02 | Approve & Complete | Cashier opens, approves | Voucher posts, stock deducted, receipt | P1 | Pass |
| TC-SALE-CA-03 | Cashier edits qty/discount/tender | Modify then approve | Final values used; edit visible in details | P1 | **Fail** BUG-SALE-034 |
| TC-SALE-CA-04 | Complete all | Several pending | All approved; none duplicated | P2 | Pass |
| TC-SALE-CA-05 | Search queue | Invoice, customer, phone, seller | Filters | P3 | **Fail** BUG-SALE-018 |
| TC-SALE-CA-06 | Reject/cancel pending |  | The queue offers reject / cancel and the stock is released (answer 9) | P2 | **Fail** BUG-SALE-060 |
| TC-SALE-CA-07 | Reserved stock visibility | Pending sale of last unit; another user searches | Stock is deducted at once when the sale enters the queue (answer 9) | P1 | Pass (stock drops when the sale is sent to the queue) |
| TC-SALE-CA-08 | Permission | Salesperson opens /cashier | Denied or read-only | P1 | Blocked (needs a non-owner login) |
| TC-SALE-CA-09 | Queue page when feature OFF | `/cashier` with Separate Cashier OFF | Opens, empty (OBS-SALE-006) | P3 | Pass |
| TC-SALE-CA-10 | Toggle ON while pending items exist then OFF | | Pending items still approvable | P2 | Pass |
| TC-SALE-CA-11 | Dashboard/Sale Record before approval | | Pending excluded from totals; visible with status filter | P1 | **Fail** BUG-SALE-021 |
| TC-SALE-CA-12 | Cashier can modify quantities of a queued sale (SRS 6.3) | Open a queued sale in /cashier; look for a quantity control | Quantity (and items) editable before Approve & Complete | P2 | **Fail** BUG-SALE-045 |
| TC-SALE-CA-13 | Approve & Complete generates the final receipt (SRS 6.4) | Approve a queued sale | Receipt (print/PDF) produced; voucher posted; stock deducted | P2 | **Fail** BUG-SALE-050 |

### 5.10 Sale Record and post-sale operations (SR)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-SR-01 | List & tiles | Open Sale Record | Tiles Total Sales/Collected/Profit/Due; grid columns Id/Date, Customer, Qty, Bill, Paid, Status, Sold By, Profit, Action | P2 | **Fail** BUG-SALE-047 |
| TC-SALE-SR-02 | Tiles = grid | After sales | Tile sums equal visible/filtered rows | P1 | **Fail** BUG-SALE-010 |
| TC-SALE-SR-03 | Search | invoice no, customer name, phone, none | Correct | P2 | **Fail** BUG-SALE-018 |
| TC-SALE-SR-04 | Filters | Date range, Status, Payment Method, Channel, Sold By, combined, Reset | Correct; start > end rejected | P2 | **Fail** BUG-SALE-048 |
| TC-SALE-SR-05 | Sorting & paging | Columns, 10/20/50, page jump | Stable | P3 | Blocked (columns are not sortable - gap; paging 10/page confirmed) |
| TC-SALE-SR-06 | View Details | Open sale | Items, batches, cost, discounts, round-off, payments, cashier approval, profit | P1 | **Fail** BUG-SALE-015 |
| TC-SALE-SR-07 | Edit sale | Change qty / price / payment | Stock, ledger, treasury, profit recomputed; Sale Edit History row: user, time, before/after | P1 | Pass (qty 2 -> 1 saved: bill Tk 100 -> Tk 50; Change History row created) |
| TC-SALE-SR-08 | Edit validations | qty 0, > stock (OOS OFF), loss price (Loss OFF) | Same rules as POS | P1 | Pass (below-cost price rejected on update; a sale with a return is 'not editable') |
| TC-SALE-SR-09 | Pay Due | Due sale; pay partial / full / over | Due reduced; voucher printable; Due Collect and customer ledger updated | P1 | Pass |
| TC-SALE-SR-10 | Cancel sale | Cancel completed sale | Stock restored to the original batches; ledger/treasury reversed; status Cancelled; audit log | P1 | Pass |
| TC-SALE-SR-11 | Cancel with returns / collections |  | Cancel refused once the sale has a return (cancel the return first); no reason required (answer 6) | P1 | **Fail** BUG-SALE-039 |
| TC-SALE-SR-12 | Cancel confirmation + double-click | | Confirm dialog; single reversal | P1 | Pass (double-click Yes, cancel it: one request, stock +1) |
| TC-SALE-SR-13 | Edit/cancel after Cash Closer | | Defined behaviour | P2 | Blocked (Cash Closer auto-saves on open, so no explicit closed state to test against) |
| TC-SALE-SR-14 | Reprint | Print invoice | Matches Invoice Config (logo, footer) | P3 | Pass (Sale Details > Print Receipt generates an 80 mm PDF) |
| TC-SALE-SR-15 | Permission | Staff without edit/cancel right; direct API | 403 | P1 | Blocked (needs a non-owner login) |
| TC-SALE-SR-16 | Invoice Config effect | Change invoice template | Printed invoice reflects it | P3 | Blocked (the receipt is a PDF with embedded fonts; its text cannot be asserted without a PDF parser; Invoice Config saved and restored) |
| TC-SALE-SR-17 | Sale Edit History entries are immutable (SRS 7.1) | Open Sale Edit History of an edited sale; look for edit/delete controls; try the API | Entries cannot be edited or deleted | P2 | Pass (history entries expand to Field / From / To; the only control is a date search; the API was not tried) |
| TC-SALE-SR-18 | Pay Due prints a payment voucher (SRS 7.1) | Collect a due payment; use the voucher/print option | Voucher shows invoice, amount, method, balance | P3 | **Fail** BUG-SALE-049 |

### 5.11 Sale return (RT)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-RT-01 | Entry | /sale-return and "Return Sale" from Sale Record | Empty state "No sale selected"; record entry pre-loads sale | P2 | Pass (empty) |
| TC-SALE-RT-02 | Search sale | Invoice no, customer; unknown | Found / "no result" | P2 | **Fail** BUG-SALE-018 |
| TC-SALE-RT-03 | Proportional refund | SRS example: A 2 x 100, B 1 x 300, overall disc 50; return 1 A | Refund 90 (not 100) | P1 | Pass |
| TC-SALE-RT-04 | Full return | Return all | Sum refunds = amount paid; stock restored | P1 | Pass |
| TC-SALE-RT-05 | Partial qty | Return 1 of 2 | Qty limit = sold - already returned | P1 | Pass (the server rejects an over-return: 'exceeds the remaining 0 on this line') |
| TC-SALE-RT-06 | Over-return | Qty > sold; second return beyond remaining | Blocked | P1 | **Fail** BUG-SALE-020 |
| TC-SALE-RT-07 | Qty boundaries | 0, -1, 0.5, text | Rejected | P1 | **Fail** BUG-SALE-020 |
| TC-SALE-RT-08 | Line-discounted item | Return item with line discount | Net price uses line discount then allocated adjustment | P1 | Pass (line discount and the overall share are used: TEST PRODUCT 2 pcs = Tk 81; rounding: BUG-SALE-038) |
| TC-SALE-RT-09 | With loyalty / less / profit / round-off adjustments | | Net Adjustments formula (SRS 7.2) | P1 | Pass |
| TC-SALE-RT-10 | Restored to original batch | Multi-batch sale | Each batch gets its pieces back | P1 | Pass (automated: after returning a whole sale the pieces went back to the batch they came from) |
| TC-SALE-RT-11 | Profit report | After return | Realised profit of returned units removed from Sale Record, Dashboard, Analytics | P1 | Pass |
| TC-SALE-RT-12 | Refund settlement | Cash; reduce Due; credit Advance (Registered) | Registered customer: cash or reduce the balance, the seller's choice; cash falls, stock and stock value rise (answer 7) | P1 | **Fail** BUG-SALE-009 |
| TC-SALE-RT-13 | Walk-in refund |  | Walk-in refund is cash; cash falls, stock and stock value rise (answer 7) | P1 | **Fail** BUG-SALE-009 |
| TC-SALE-RT-14 | Cancelled / pending sale | Return of cancelled or pending sale | Blocked | P1 | **Fail** BUG-SALE-019 |
| TC-SALE-RT-15 | Sale Return Record | List, filter, details | Lists the return, links to sale | P2 | **Fail** BUG-SALE-011 |
| TC-SALE-RT-16 | Double-click return | | One return | P1 | **Fail** BUG-SALE-057 |
| TC-SALE-RT-17 | Refund reduces the customer's Due when the customer owes money (SRS 7.2) | Registered customer with a Due returns an item | Seller chooses Cash or reduce Due / Advance (answer 7) | P1 | **Fail** BUG-SALE-059 |
| TC-SALE-RT-18 | A return appears in the Customer Ledger (SRS 3.2 / 7.2) | Return an item for a registered customer; open Customer Ledger | Chronological ledger line for the return with running balance | P2 | Blocked (Customer Ledger shows static demo data: BUG-SALE-007) |

### 5.12 Dashboard and cross-module reconciliation (DB)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-DB-01 | Dashboard loads | Open Dashboard | Widgets render, no errors | P2 | Pass |
| TC-SALE-DB-02 | Sale Summary = Sale Record | Same period | Sales, Due Sale, Customer Return equal | P1 | **Fail** BUG-SALE-004 (to confirm) |
| TC-SALE-DB-03 | Staff Performance = Sale Record by Sold By | | Invoices/revenue/profit equal | P1 | **Fail** BUG-SALE-004 (to confirm) |
| TC-SALE-DB-04 | Customer Due = Customer List Due total = Due Collect total | | Equal | P1 | Pass |
| TC-SALE-DB-05 | Treasury after sale/collection/return | Cash/Card/Bank/MFS balances | Move by exact tender amounts | P1 | **Fail** BUG-SALE-009 |
| TC-SALE-DB-06 | Period filters & Compare | Today/Yesterday/7/30 days/custom/Compare | Numbers consistent, custom start > end rejected | P2 | Pass (Today/Yesterday/7/30 days and More ranges work; Compare shows no visible delta) |
| TC-SALE-DB-07 | Product Movers / Medicine Mix | After sale | Qty and revenue update | P2 | Pass |
| TC-SALE-DB-08 | Expiring Stock date | Batches without expiry | "No expiry", not 1 Jan 1970 | P3 | **Fail** BUG-SALE-005 |
| TC-SALE-DB-09 | Quick Links | Sale/Inventory/Sale Return/Cash Closer | Navigate correctly | P3 | Pass |

### 5.13 Security, permissions and non-functional (NF)

| ID | Scenario | Steps | Expected | Pri | Status |
|---|---|---|---|---|---|
| TC-SALE-NF-01 | Unauthenticated access | Log out; open `/sale`, `/sale-record`, `/customer`, `/settings/sale-config` | Redirect to /login (verified for `/sale`); API 401 | P1 | Pass (`/sale` -> /login; API 401 without token) |
| TC-SALE-NF-02 | Role matrix | Owner / Manager / Salesperson / Cashier on each route and action (discount, cancel, edit, write-off, settings) | Per RBAC; direct URL and API also enforced | P1 | Blocked (only the Owner login exists; another role needs a second sign-in, which this run cannot type) |
| TC-SALE-NF-03 | Server-side validation | Send checkout API with qty 0, negative price, paid > limit, loss price (Loss OFF), 0-stock (OOS OFF) | Rejected by API, not just UI (BUG-SALE-001 suggests UI-level only; verify) | P1 | **Fail** BUG-SALE-040 |
| TC-SALE-NF-04 | Audit trail | Loss sale, cancel, edit, OTP redeem | Log with staff id, timestamp, before/after | P1 | Pass (expanded entry lists Status, Total Price Tk 100 -> 50, Final Price, Settlement Type - -> PROFIT, Approximate Profit 85.70 -> 42.85, user and time) |
| TC-SALE-NF-05 | Precision | 0.1 + 0.2 style amounts, 2 dp internally, integer final | No float drift in Sale Record vs Details | P1 | **Fail** BUG-SALE-038 |
| TC-SALE-NF-06 | Concurrency | Same batch, two terminals | Row lock, no oversell (IV-12) | P1 | **Fail** BUG-SALE-022 |
| TC-SALE-NF-07 | XSS in names/notes | `<img onerror>` in customer, note, walk-in detail | Escaped in grid, invoice, print | P1 | Pass (HTML in customer name, walk-in detail and note is inert; nothing executed) |
| TC-SALE-NF-08 | Session expiry mid-checkout | Expire token, Complete Sale | Re-login without losing cart; no half sale | P2 | Pass (cleared cookies at checkout: 401, redirect to /login, no sale created) |
| TC-SALE-NF-09 | Performance | Search on 41,006 SKUs | Results < 2 s; no UI freeze | P3 | Pass (Dashboard 2.4 s, Sale Record 3.7 s, Customers 3.4 s, POS 3.4 s, product search 1.3 s) |
| TC-SALE-NF-10 | Cross-browser | Chromium (done), Firefox, WebKit on SALE happy path | Same | P3 | Pass (Firefox and WebKit: list, POS search, cart and checkout work; cold load 36-40 s on the dev build) |
| TC-SALE-NF-11 | Accessibility | Labels on inputs, keyboard cart flow, focus in drawer | Usable by keyboard | P3 | **Fail** BUG-SALE-033 |
| TC-SALE-NF-12 | Security log for loss sales, cancellations, invoice edits and OTP redemptions (SRS 8) | Perform each action; look for a log with staff id and time | Log entry per action | P2 | Blocked (no audit / security log view in the UI) |

## 5A. Traceability: SRS clause -> test cases

Every clause of `Knowledge/Sale Management/Sale management.md` maps to at least one case. Cases added by this review are marked (new).

| SRS clause | Requirement | Test cases |
|---|---|---|
| 2.1.1 | Out of Stock Sale ON/OFF | SC-10, SC-11, SC-12 |
| 2.1.2 | Allow Loss Sale ON/OFF | SC-13, SC-14, SC-15, SC-16 |
| 2.1.3 | Stock Quantity display | SC-17, SC-18 |
| 2.1.4 | Company / Brand name | SC-19, SC-20 |
| 2.1.5 | Profit Margin display (checkout, cashier, sales views) | SC-21, SC-22, SC-28 (new) |
| 2.1.6 | Rack / Shelf number | SC-23, SC-29 (new) |
| 2.1.7 | Separate Cashier workflow | SC-24, SC-25, CA-01..CA-13, CA-11 |
| 2.1 (all) | Settings behaviour and scope | SC-01..SC-09, SC-26, SC-27 |
| 2.2 | Earning / redemption rules, min / max, OTP | LC-01..LC-07, LY-01..LY-11 |
| 3.1 | Walk-in vs registered customer, metadata, default discount | CK-19..CK-23, LY-02, LY-03 |
| 3.2 | Customer list, profile fields, actions, ledger, bad debt, loyalty activation | CU-01..CU-28 |
| 4.1 | Retail / Wholesale modes | SC-08, PC-20, PC-25 (new) |
| 4.2 | Search, unit conversion, line discounts, hold | PC-01..PC-24, PC-26 (new), HS-01..HS-10 |
| 4.3 | Summary, overall discount and exclusion rule, loyalty discount, round-off, final price, split payments, quick print | CK-01..CK-08, CK-14..CK-18, CK-24..CK-32 |
| 4.4 | Settlement matrix | CK-02, CK-09..CK-13, CK-20 |
| 5.1 | FEFO and multi-batch deduction | IV-01, IV-02, IV-03, IV-11 |
| 5.2 | COGS and fallback cost | IV-05, IV-06, IV-07 |
| 5.3 | Proportional profit allocation | IV-08, IV-09, IV-10 |
| 6 | Cashier approval workflow | CA-01..CA-13 |
| 7.1 | Sale Record, details, edit and history, pay due, cancel | SR-01..SR-18 |
| 7.2 | Proportional return refund, restore to batch, profit, settlement | RT-01..RT-18, IV-04 |
| 8 | Precision, concurrency, audit, security | NF-01..NF-12, IV-12 |
| Dependencies | Dashboard, Treasury, Customer Due | DB-01..DB-09, IV-13, IV-14 |

## 6. Counts (computed from the Status column)

| Section | Cases | Pass | Fail | Blocked | Not run |
|---|---|---|---|---|---|
| Sale Config | 29 | 18 | 9 | 2 | 0 |
| Loyalty Config | 7 | 4 | 2 | 1 | 0 |
| Customer | 28 | 15 | 12 | 1 | 0 |
| POS / cart | 26 | 19 | 6 | 1 | 0 |
| Hold | 10 | 6 | 1 | 3 | 0 |
| Checkout | 32 | 22 | 10 | 0 | 0 |
| Inventory / profit | 14 | 7 | 5 | 2 | 0 |
| Loyalty at POS | 11 | 7 | 1 | 3 | 0 |
| Cashier | 13 | 5 | 7 | 1 | 0 |
| Sale Record | 18 | 7 | 7 | 4 | 0 |
| Return | 18 | 8 | 9 | 1 | 0 |
| Dashboard | 9 | 5 | 4 | 0 | 0 |
| Security / NF | 12 | 6 | 4 | 2 | 0 |
| **Total** | **227** | **129** | **77** | **21** | **0** |

Failed cases (77): SC-05, SC-10, SC-11, SC-16, SC-17, SC-19, SC-25, SC-28, SC-29, LC-03, LC-04, CU-06, CU-08, CU-10, CU-11, CU-12, CU-13, CU-14, CU-18, CU-20, CU-22, CU-24, CU-26, PC-08, PC-13, PC-14, PC-20, PC-22, PC-24, HS-02, CK-05, CK-06, CK-10, CK-13, CK-15, CK-20, CK-22, CK-25, CK-30, CK-31, IV-06, IV-07, IV-10, IV-12, IV-13, LY-10, CA-01, CA-03, CA-05, CA-06, CA-11, CA-12, CA-13, SR-01, SR-02, SR-03, SR-04, SR-06, SR-11, SR-18, RT-02, RT-06, RT-07, RT-12, RT-13, RT-14, RT-15, RT-16, RT-17, DB-02, DB-03, DB-05, DB-08, NF-03, NF-05, NF-06, NF-11. Each is logged in `PMS_Product_Module_Test_Report.xlsx` (Module = Sale) against a bug in BUG-SALE-001..060 on its Bug Logs sheet.

## 7. Blocked cases and what they need

Every case has a result except the Not run ones listed in the counts. 21 cases are Blocked: SC-09, SC-27, LC-07, CU-23, PC-21, HS-01, HS-05, HS-10, IV-11, IV-14, LY-08, LY-09, LY-11, CA-08, SR-05, SR-13, SR-15, SR-16, RT-18, NF-02, NF-12.

| Reason | Cases | What would unblock them |
|---|---|---|
| Needs a non-owner login (this run cannot type a second password) | SC-09, LC-07, CA-08, SR-15, NF-02, HS-10 | A Cashier and a Salesperson account whose sign-in is done by the tester |
| Needs a multi-batch / small-batch product | IV-14, PC-21 (IV-02, IV-03, IV-07 and RT-10 were verified with batches bought through Inventory) | Seed a product with 2+ batches of different expiry, one with a tiny batch, one without price (Inventory purchases / Stock Adjust) |
| Requirement gap (still open after the answers in section 4) | SC-04 (no prompt by design?), SC-27, HS-01, HS-10, SR-13, LY-09 | Answers on hold expiry / resume rights, cancel after Cash Closer, points on a due sale. HS-05 is now executable (answer 5) |
| Would SMS a number the tester does not own | CU-23 | A test phone number |
| Not observable from the UI | LY-08, LY-11, SR-13, SR-16 | Manual points entry / audit view / reject action / explicit cash-closed state / PDF text parser |

Test data created on staging by this run (not removable from the UI): sales #SALE_20261027_01 to _33 (including returns, a cancelled sale, a loss sale, two duplicates from the double-click bug and a walk-in sale with Due Tk 49), customers Manik Hossain (Advance Tk 199), QA Due Cust (Due Tk 400, past due date), QA Page 1-5, QA Edited One (inactive), QA Test x2, QA Inline Cust, a customer whose name is an HTML tag and a merged-name customer, NAPA 500 MG stock -2 and lower TEST PRODUCT stock. Sale Config, Loyalty Config and Invoice Config were restored to their original values.

## 8. Recommended automation (not built yet)

- **API/UI smoke (P1):** SC-10/11/17/19, PC-06, CK-02/09/10/11/12, IV-03, RT-03 - after BUG-SALE-001..003 are fixed.
- **Oracle tests** (like `tests/inventory/default_mode/test_default_calc_oracle.py`): checkout Final Price, round-off, proportional allocation, return refund (SRS 7.2 example).
- **FEFO (built, `tests/sale/test_fefo_batches.py`, run 2026-10-29 headed):** the fixture buys two batches of 3BIOTIC 100GM through Inventory (later expiry first). `earliest-expiry batch` PASSED (IV-02); `return restores the source batch` PASSED (RT-10); `spill into batch 2` PASSED (IV-03); `oversell is costed` FAILED: with two batches in stock, selling 2 pcs beyond all stock shows the line's Cost as 'Pending' instead of the fallback cost (IV-07, BUG-SALE-041 confirmed). The first two runs of this file errored at set-up because 3BIOTIC 100GM was at -2 pcs and the stock reader could not parse a minus sign (fixed).
- **Run 2026-10-29 (headed, fresh session):** `test_return_beyond_remaining_is_refused` PASSED (the form disables Go to Return Checkout above the remaining quantity). The other 7 (4 checkout-regression, expired batch, walk-in overpayment, hold double-click) failed in the test set-up, not in the product: the `default_config` fixture navigated to Settings after the `sale` fixture had opened the POS, so `#productId` was gone. Fixed by making `sale` depend on `default_config`.
- **Re-run of those 7 (2026-10-29, headed, fresh session, 41 min): 6 failed on the bugs, 1 passed.** Reproduced: BUG-SALE-037 (overall 10 % took Tk 16 off instead of Tk 7, the line-discounted item was included), BUG-SALE-022 (one double click created two sales, both id 201), BUG-SALE-040 (a walk-in paid Tk 1 of Tk 50 was created with status 201), BUG-SALE-030 (1 piece of expired 3-C sold with no warning), BUG-SALE-008 (a walk-in overpayment, Tk 80 on Tk 50, saved as 'Advance'), BUG-SALE-056 (one cart produced 2 holds). Not reproduced: BUG-SALE-023 - a 10 % line discount taking the net price (4.50) below cost was blocked with 400 'below cost' (the original finding used 40 %, Tk 10 to Tk 6). SC-16 stays Fail until the 40 % case is re-checked by hand.
- **Built:** `tests/sale` and `tests/settings` (config restore fixtures, high-bug regressions, double-submit family); see the page objects under `pages/` and `pages/settings/`.
- **Config restore fixture:** snapshot `sales-configs`, toggle, assert, restore in `finally` (same pattern as Inventory Config).
- Page objects: extend `pages/sale_page.py` (today only product/qty/add/checkout/complete) with config, record and customer pages.
