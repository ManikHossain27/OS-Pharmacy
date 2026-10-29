"""Sale Management test cases for the Excel report.

The cases themselves live in docs/SALE_MANAGEMENT.md (section 5 tables); this module parses them into catalog `TC`
rows so the doc stays the single source. Only cases executed on staging carry an `Actual Result` (ACTUAL below).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "SALE_MANAGEMENT.md"
BUGS = Path(__file__).resolve().parent.parent / "test_data" / "bug_logs.json"

PRECOND = "Logged in as pms_tc11@gmail.com (Owner); Manik Pharma selected and verified in the sidebar"
PRIORITY = {"P1": "High", "P2": "Medium", "P3": "Low"}
DATA = "Customer Manik Hossain (+8801521503629, loyalty member) where a customer is needed"

# section code -> (Module, Feature)
SECTIONS = {
    "SC": ("Sale", "Sale Config"),
    "LC": ("Sale", "Loyalty Config"),
    "CU": ("Sale", "Customer List"),
    "PC": ("Sale", "POS - product search and cart"),
    "HS": ("Sale", "POS - Hold sale"),
    "CK": ("Sale", "POS - Checkout, payment and settlement"),
    "IV": ("Sale", "Inventory deduction, COGS and profit"),
    "LY": ("Sale", "Loyalty at POS"),
    "CA": ("Sale", "Cashier approval workflow"),
    "SR": ("Sale", "Sale Record and post-sale operations"),
    "RT": ("Sale", "Sale Return"),
    "DB": ("Cross-module", "Dashboard reconciliation"),
    "NF": ("Platform", "Sale - security and non-functional"),
}

# id -> (actual result, bug id, evidence, remarks) for cases executed on staging 2026-10-27
ACTUAL = {
    "TC-SALE-SC-01": ("Seven toggles + Business Type shown; all OFF, Retail; matches GET sales-configs/598.", "", "", ""),
    "TC-SALE-SC-10": ("Search 'napa' lists 5 options, all '0 pcs 0 box', with Out of Stock Sale OFF.", "BUG-SALE-001", ".playwright-mcp/sale-search-oos-off.png", ""),
    "TC-SALE-SC-17": ("'0 pcs / 0 box' shown in the dropdown and the cart Stock column with Stock Qty OFF.", "BUG-SALE-002", ".playwright-mcp/sale-cart-oos.png", ""),
    "TC-SALE-SC-19": ("'BEXIMCO PHARMACEUTICALS LTD.' shown in the dropdown and the product detail line with Company Name OFF.", "BUG-SALE-003", ".playwright-mcp/sale-selected.png", ""),
    "TC-SALE-SC-21": ("Checkout shows no profit/margin with Profit Margin OFF.", "", ".playwright-mcp/sale-checkout.png", ""),
    "TC-SALE-SC-23": ("No rack number shown with Rack Number OFF (ON state not exercised).", "", "", ""),
    "TC-SALE-LC-01": ("Four numeric fields (Earning Tk/pt, Redemption pts/Tk, Min redeem, Max redeem); all 0.", "", "", ""),
    "TC-SALE-CU-01": ("Empty pharmacy: tiles 0, 'No customers found'.", "", "", ""),
    "TC-SALE-CU-02": ("Drawer shows Name*, Phone*(+880), Address, Balance Advance/Due, Discount %, Due Payment Date, Status Active, Loyalty Member Inactive, Note.", "", ".playwright-mcp/customer-add.png", ""),
    "TC-SALE-CU-12": ("Cancel closed the empty drawer; nothing saved.", "", "", "Filled-form cancel not tested."),
    "TC-SALE-CU-20": ("Ledger lists 7 records (#INV-31, #INV-32, #PAY-CUS-33..37) and opening balance Tk 100 Cr for a customer with 0 orders and Tk 0 balance; no ledger API call.", "BUG-SALE-007", ".playwright-mcp/cust-ledger.png", ""),
    "TC-SALE-CU-21": ("Payment History: balance Tk 0, 0 payments, 'No payments recorded yet', 'Add New Payment' button.", "", "", "Tender grouping not tested (no payments)."),
    "TC-SALE-CU-26": ("Drawer shows 'Nusrat Jahan', 01912-345680, Advance Tk 2,600, 10% discount, 11 points, 3 orders / Tk 21,400 and 3 recent invoices; no API call; list/API say Manik Hossain, 0 pts, 0 orders.", "BUG-SALE-006", ".playwright-mcp/cust-details.png", ""),
    "TC-SALE-CU-27": ("Menu: View Details, Customer Ledger, Payment History, Edit. Add Payment is inside Payment History; its Payment Type offers Payment / Return / Bad Debts.", "", "", ""),
    "TC-SALE-CU-28": ("GET customers/598: Manik Hossain, +8801521503629, loyaltyPoint 0, totalOrders 0, balance 0, active - equals the list row.", "", "", ""),
    "TC-SALE-PC-01": ("'Cart is empty', Retail selected, Hold List 0, Hold/Checkout disabled, Total Tk 0.00.", "", "", ""),
    "TC-SALE-PC-02": ("'napa' returns 5 NAPA variants with strength, form, generic and company.", "", ".playwright-mcp/sale-search-oos-off.png", ""),
    "TC-SALE-PC-05": ("Selecting NAPA 500 MG fills price 1.20/pc and shows Last Purchase Tk 1.06, Qty/Box 510.", "", ".playwright-mcp/sale-selected.png", ""),
    "TC-SALE-PC-06": ("5 pcs added: row 5 pc, Sale/pc 1.20, Sale/bx 612.00, price Tk 6.00, Cart Items 1, total Tk 6.00.", "", ".playwright-mcp/sale-cart-oos.png", "Product had 0 stock (see BUG-SALE-001)."),
    "TC-SALE-PC-16": ("Trash icon removes the line immediately; cart empty; no confirmation.", "", "", "No confirmation (OBS-SALE-007)."),
    "TC-SALE-PC-18": ("Cart still held 1 item after a full reload of /sale.", "", "", "Clearing after Complete Sale not tested."),
    "TC-SALE-HS-09": ("Hold Current Sale is disabled while the cart is empty.", "", "", ""),
    "TC-SALE-CK-01": ("Checkout shows items, Total Price, Discount, Round Off, Final Price, Total Paid, Due; paid pre-filled = final.", "", ".playwright-mcp/sale-checkout.png", ""),
    "TC-SALE-CK-03": ("10 % on Tk 120 -> Discount Amount Tk 12.00, Final Price Tk 108.00.", "", "", "Sale not completed."),
    "TC-SALE-CK-05": ("150 and -5 stay in the box; discount amount remains Tk 0.00; no message.", "", "", "OBS-SALE-008: no feedback. 0, = total, text not tested."),
    "TC-SALE-CK-11": ("Customer Manik Hossain, final 120, paid 100 -> New Balance (Due) Tk 20.00, Due Tk 20.00.", "", "", "Preview only; Complete Sale not clicked."),
    "TC-SALE-CK-12": ("Paid 150 -> New Balance (Adv.) Tk 30.00, Due Tk 0.00.", "", ".playwright-mcp/checkout-paid150.png", "Preview only; Complete Sale not clicked."),
    "TC-SALE-CK-21": ("Search 'Manik' returns 'Manik Hossain (+8801521503629)'; panel shows Previous Balance (Adv.) Tk 0.00, New Balance, Loyalty Points 0 and 'Apply Max Loyalty Points'.", "", ".playwright-mcp/checkout-customer.png", "OBS-SALE-009."),
    "TC-SALE-CA-09": ("/cashier opens with 'Queue is Empty' while Separate Cashier is OFF.", "", "", "OBS-SALE-006: requirement gap."),
    "TC-SALE-SR-01": ("Tiles Total Sales (0)/Collected/Profit/Due Tk 0; grid columns as listed; filters Search, Date Range, Status, Payment Method, Channel, Sold By, Reset.", "", ".playwright-mcp/sale-record.png", ""),
    "TC-SALE-RT-01": ("/sale-return shows 'No sale selected', search box and 'Go to Return Checkout'.", "", "", "Return Sale entry from Sale Record not tested (no sales)."),
    "TC-SALE-DB-01": ("Dashboard loaded with all widgets.", "", "", ""),
    "TC-SALE-DB-02": ("Sale Summary: Sales Tk 0, Profit Tk 0 (Today); Sale Record: 0 sales (no date filter).", "BUG-SALE-004", "", "To confirm: Staff Performance period."),
    "TC-SALE-DB-03": ("Staff Performance: Owner 3 / Tk 3,371, Nusrat Jahan 2 / Tk 796, Karim Ahmed 2 / Tk 656 while Sale Record has 0 sales.", "BUG-SALE-004", "", "To confirm."),
    "TC-SALE-DB-08": ("Expiring Stock rows read '1 Jan 1970 - expired 20753d ago'.", "BUG-SALE-005", "", ""),
    "TC-SALE-NF-01": ("Fresh session: /sale redirected to /login; direct API call without the app token returned 401.", "", "", "Other routes not tried."),
}


# second execution round (2026-10-27): real test sales on TEST PRODUCT 1200 (cost 7.32/pc, sale 50/pc), customer Manik Hossain
ACTUAL.update({
    "TC-SALE-SC-11": ("Cart accepted Qty 99,99,99,999 pcs for TEST PRODUCT (stock 1,08,413) with Out of Stock Sale OFF; checkout not exercised.", "BUG-SALE-001", "", "Checkout-time stock check not verified."),
    "TC-SALE-SC-13": ("Price 6.00 passed the cart; Complete Sale was blocked with 'Selling TEST PRODUCT below cost is not allowed for this pharmacy.' (FEFO cost 7.32/pc); no sale created.", "", "", "OBS-SALE-010: message does not state the cost."),
    "TC-SALE-SC-24": ("With Separate Cashier OFF, Complete Sale finalised at once: Sale Record row, stock, Treasury and Dashboard updated.", "", "", ""),
    "TC-SALE-PC-04": ("No crash for NAPA/napa/padded, 1 char, ', <b>, 200 chars, Bangla (0 results for ' and Bangla). '%' returns unrelated products (wildcard).", "", "", "Parallel worker A."),
    "TC-SALE-PC-07": ("Blank or text Qty -> 'Qty is required'; nothing added.", "", "", ""),
    "TC-SALE-PC-08": ("Qty 0 and -1: nothing added, no message; 0.5 -> 1 pc and 2.5 -> 3 pc silently; 99,99,99,999 accepted.", "BUG-SALE-016", "", ""),
    "TC-SALE-PC-09": ("Sale/bx = Tk 500.00 for Sale/pc Tk 50.00 with 10 pcs/box; Box line added as '1 box'.", "", "", "Stock deduction by box not run."),
    "TC-SALE-PC-10": ("0, -1, 0.001, 1.234 -> 'Sale price can't be less than purchase price'; 50.5 accepted (Sale/bx 505.00); 10,00,00,000 accepted.", "", "", "No upper limit (BUG-SALE-016)."),
    "TC-SALE-PC-11": ("3 pc x Tk 50 with 10 % -> Disc 10 %, line Tk 135.00 (was 150.00), total Tk 135.00.", "", "", ""),
    "TC-SALE-PC-12": ("Tk 50 and Tk 100 line discounts on 2 pc x 50 were accepted and added.", "", "", "Resulting totals not read."),
    "TC-SALE-PC-13": ("101 % and Tk 101 on a Tk 100 line -> 'Discount must not be greater than total price'; 100 % and Tk 100 accepted; -1 % accepted (shown as '-').", "BUG-SALE-016", "", ""),
    "TC-SALE-PC-20": ("Wholesale shows Last Purchase/box Tk 33.20, Sale Price/box Tk 50.00, Qty Box; the click also saved businessType WHOLESALE for every session (PUT sales-configs/update/598); restored to RETAIL.", "BUG-SALE-014", "", ""),
    "TC-SALE-HS-01": ("Hold Current Sale held the cart immediately; no note field was offered.", "", ".playwright-mcp/hold-list.png", "SRS: optional reference note."),
    "TC-SALE-HS-02": ("Hold without note: cart cleared, Hold List badge 1; list shows Hold Id 1, Walk in Customer, 27 Oct 2026 01:21 pm, 1 items, Tk 135.", "", ".playwright-mcp/hold-list.png", ""),
    "TC-SALE-HS-03": ("Resume restored 3 pc, Tk 50, 10 %, Tk 135.00; entry removed; Hold List badge 0 and disabled.", "", "", ""),
    "TC-SALE-CK-02": ("#SALE_20261027_01: Tk 100 paid CASH, status Paid, profit 85.36; stock -2; Treasury cash +100; Dashboard Sales Tk 100.", "", ".playwright-mcp/sale1-details.png", ""),
    "TC-SALE-CK-09": ("Dialog 'Payment Shortfall - Settlement Choice' > Less & Sale / Discount: #SALE_20261027_02 bill Tk 80 (-Tk 20 disc), Paid, profit 65.36 (85.36 - 20); Treasury +80.", "", ".playwright-mcp/underpay-after.png", ""),
    "TC-SALE-CK-10": ("Dialog 'Excess Payment' says return Tk 30 change; saved sale #SALE_20261027_03 shows Paid Tk 130, Due 0, status Advance, profit 85.36; Treasury +130; Dashboard profit +30.", "BUG-SALE-008", ".playwright-mcp/overpay-state.png; .playwright-mcp/sale3-details.png", ""),
    "TC-SALE-CK-11": ("Manik Hossain, paid 60 of 100, 'Due & Sale': #SALE_20261027_04 Paid 60, Due 40; customer Due Tk 40, orders 1, spent Tk 100; Sale Record Due tile Tk 40.", "", ".playwright-mcp/sale4-state.png", ""),
    "TC-SALE-CK-20": ("Walk-in overpay sale was saved with status 'Advance' although a walk-in cannot hold a balance.", "BUG-SALE-008", ".playwright-mcp/sale3-details.png", ""),
    "TC-SALE-IV-01": ("Stock 1,08,418 -> 1,08,411 after 4 sales (8 pcs) and a 1-pc return; -> 1,08,413 after cancelling #01.", "", "", ""),
    "TC-SALE-IV-05": ("Sale Details: 2 pc, Cost Tk 14.64 (Tk 7.32/pc), Profit Tk 85.36 = 100 - 14.64.", "", ".playwright-mcp/sale1-details.png", ""),
    "TC-SALE-IV-09": ("Less & Sale deficit of Tk 20 cut profit from 85.36 to 65.36 on the single line.", "", "", "Multi-line allocation not run."),
    "TC-SALE-IV-13": ("After the sales: Sale Record profit 321 vs Dashboard 351; Sale Record tiles still include the cancelled sale while Dashboard excludes it.", "BUG-SALE-008", "", "See BUG-SALE-010."),
    "TC-SALE-SR-02": ("After cancelling #01 the tiles stay Total Sales (5) Tk 410 / Collected Tk 385 / Profit Tk 289 (cancelled sale and return counted).", "BUG-SALE-010", "", ""),
    "TC-SALE-SR-06": ("Sale Details lists Channel, Customer, Pricing Breakdown, items with Cost and Profit; no batch / expiry breakdown.", "BUG-SALE-015", ".playwright-mcp/sale1-details.png", ""),
    "TC-SALE-SR-09": ("Pay Due drawer (Payment / Return / Bad Debts, amount, method CASH/BANK/CARD/MFS, note): Tk 15 on Due 40 -> sale Paid 75 / Due 25, customer Due 25, Cash +15; amounts 0, -5 rejected ('must be greater than 0'); 100 previews Advance Tk 60.", "", ".playwright-mcp/paydue-15.png", "Voucher print not run; 40.5 previews 'Advance Tk 1' (rounding)."),
    "TC-SALE-SR-10": ("Cancel Sale #01: status Cancelled; stock +2 (1,08,413); Cash -100 ('out Tk 100'); Dashboard Sales 380 -> 280.", "", "", "Tiles: BUG-SALE-010."),
    "TC-SALE-SR-12": ("Dialog 'Cancel this sale? ... Keep it / Yes, cancel it'; Keep it left the sale Paid; Yes cancelled it.", "", ".playwright-mcp/cancel-dialog.png", "No reason field; double-click not run."),
    "TC-SALE-RT-03": ("Sale #02 (Tk 100, Less Tk 20): returning 1 of 2 pcs shows Return to Customer Tk 40.00 (Total was Tk 80, Revised Tk 40).", "", ".playwright-mcp/return-checkout2.png", ""),
    "TC-SALE-RT-05": ("Partial return of 1 of 2 pcs completed ('Sale return has been submitted successfully').", "", "", "Over-return not run (worker C failed)."),
    "TC-SALE-RT-09": ("Net realised price used the Tk 20 less-deficit (40 not 50).", "", "", ""),
    "TC-SALE-RT-10": ("Product stock rose 1,08,410 -> 1,08,411 after the return. FEFO test: after returning a whole sale the pieces went back to the earlier-expiry batch they came from.", "", "", "Automated: tests/sale/test_fefo_batches.py::test_return_restores_the_source_batch (PASSED 2026-10-29)."),
    "TC-SALE-RT-11": ("Dashboard Sale Summary: Customer Return Tk 40, Profit 351 -> 319; Sale Record Profit 321 -> 289 (-32).", "", "", ""),
    "TC-SALE-RT-12": ("Cash refund of Tk 40: Cash stayed Tk 3,29,740, 'out Tk 0', Total Treasury 33,23,620, Cash Closer expected Tk 385.", "BUG-SALE-009", "", ""),
    "TC-SALE-RT-13": ("Walk-in return refund did not reduce Treasury cash (see RT-12).", "BUG-SALE-009", "", ""),
    "TC-SALE-RT-15": ("Return Record lists '#SALE_20261027_05', Return Amount Tk 40.00, Active; tile 'Total Sales (1) / Tk 0'; Sale Record tile became Total Sales (5).", "BUG-SALE-011", "", ""),
    "TC-SALE-DB-04": ("Customer Due Tk 25 on Dashboard = Customer List Due 25 = Sale Record Due 25; Due Collect Total due matched (40 earlier).", "", "", "BUG-SALE-012: due not listed in tabs."),
    "TC-SALE-DB-05": ("Sale +100/+80/+130/+60 and collection +15 hit Cash exactly; cancel -100 reversed; the Tk 40 return refund did not.", "BUG-SALE-009", "", ""),
    "TC-SALE-DB-07": ("Product Movers: TEST PRODUCT 6 pcs, Tk 280, 100 % after sales 1-3.", "", "", ""),
    "TC-SALE-CU-14": ("Name, case, partial name/phone, '+880152', padded and unmatched ('zzz' -> No customers found) all correct; '%' freezes the list (URIError).", "BUG-SALE-013", ".playwright-mcp/customer-percent.png", ""),
    "TC-SALE-CU-18": ("Collected Tk 15 of Due 40 -> Due 25 (customer, sale, Dashboard Customer Due); Cash +15.", "", ".playwright-mcp/paydue-15.png", "Over-payment previewed as Advance."),
    "TC-SALE-CU-24": ("After one sale: Total Orders 1, Total Spent Tk 100, Balance Due Tk 25 (after Tk 15 paid).", "", "", ""),
})


def _type(scn: str, steps: str) -> str:
    t = (scn + " " + steps).lower()
    if "boundar" in t:
        return "Boundary"
    if any(w in t for w in ("invalid", "reject", "block", "denied", "unauth", "empty submit", "required", "duplicate", "over-", "cannot", "wrong")):
        return "Negative"
    return "Positive"


ACTUAL.update({
    "TC-SALE-CU-03": ("Name 'QA Test' + phone 1712345678 created: listed as +8801712345678, balance Tk 0, orders 0, loyalty '-', Active.", "", "Customer List 2026-10-27 (screenshot not kept)", "Created by the parallel worker; two QA Test customers now exist."),
    "TC-SALE-CU-05": ("Empty: 'Customer full name is required' + 'Phone number is required'; name only -> phone message; phone only -> name message; drawer stays open.", "", "", ""),
    "TC-SALE-CU-06": ("3 digits -> 'Enter a valid phone number, e.g. 1712345678'; 8 digits -> same message; letters are stripped by the field (empty -> required).", "", "", "14 digits / 0000000000 not verified."),
    "TC-SALE-CU-09": ("Discount 101 saved as 100 (Edit shows 100) with no message.", "", "", "OBS-SALE-016; -1 / text not run."),
    "TC-SALE-CU-15": ("Status options Active/Inactive; Channel Online store/Counter only; tabs Advance 1 and Loyalty 1 list the customer; Reset Filters restores the list.", "", "", "Due tab click timed out in the worker."),
    "TC-SALE-CK-12": ("Manik Hossain (Due 25) paid 80 on a 50 bill -> Excess dialog 'Advance & Sale'; sale #SALE_20261027_06 Advance, Cash +80; customer Advance Tk 5 (25 due offset by 30).", "", "Checkout dialog observed 2026-10-27 (screenshot not kept)", "Settlement correct; preview wrong: BUG-SALE-017."),
    "TC-SALE-CK-13": ("Customer with Due Tk 25 shown as 'Previous Balance (Adv.) Tk 25.00'; New Balance (Adv.) Tk 55.00; dialog 'Current Due: Tk 0.00'.", "BUG-SALE-017", "Checkout dialog observed 2026-10-27 (screenshot not kept)", ""),
    "TC-SALE-CK-16": ("Walk-in, Tk 30 CASH + Tk 20 CARD (+ button adds a row; Due auto-updates to 0): sale #SALE_20261027_07 Paid, payments 'CASH | CARD', profit Tk 42.68.", "", "split-payment checkout (screenshot not kept)", "Per-tender treasury split not checked."),
    "TC-SALE-SR-03": ("Search 20261027_04, Manik, 8801521503629 and 'Manik' with spaces find #04; full id SALE_20261027_02, 20261027_02 and 'walk' return no rows; '_02' returns #06 and #04.", "BUG-SALE-018", "", ""),
    "TC-SALE-SR-04": ("Status options Paid/Due/Cancelled/Returned (Cancelled -> 1 row); Payment CASH 3 rows / CARD 1 row; Channel Counter (POS)/Online Store; Sold By empty.", "", "", "OBS-SALE-013; date range not run."),
    "TC-SALE-SR-05": ("Headers have no sorters; paging shows 'Showing 1-6 of 6', 10 per page.", "", "", "OBS-SALE-014."),
    "TC-SALE-SR-07": ("Row Actions > Edit Sale opens /sale/edit/62 with the sale lines, Retail/Wholesale, search and cart.", "", "", "Saving an edit and Edit History not run."),
    "TC-SALE-RT-06": ("Return Qty 3 on a 2-pc sale: box keeps 3, refund capped at Tk 100, no message.", "BUG-SALE-020", "", "Complete Return not attempted. Automated 2026-10-29: a second return above what is left is refused (Go to Return Checkout is disabled) - tests/sale/test_sale_return.py::test_return_beyond_remaining_is_refused PASSED."),
    "TC-SALE-RT-07": ("0 and -1 accepted (refund Tk 0), 0.5 -> Tk 25, 'abc' kept in the box; no inline error.", "BUG-SALE-020", "", ""),
    "TC-SALE-RT-14": ("Return Sale on Cancelled #SALE_20261027_01 opens /sale-return?saleId=59 with the lines, no block or message.", "BUG-SALE-019", "", "Complete Return not attempted."),
})

ACTUAL.update({
    "TC-SALE-SC-02": ("PUT sales-configs/update/598 sent all fields; after Save the toggles stay (reload) for outOfStockSale, allowLossSale, stockQty, companyName, profitMargin, rackNo and separateCashier; each restored to OFF afterwards.", "", "", "Toggles were saved together, not one at a time."),
    "TC-SALE-SC-06": ("After saving, /sale in the same session applied the changes (Rack No column, Approximate Profit line) without re-login.", "", "", ""),
    "TC-SALE-SC-12": ("Out of Stock Sale ON: 2 pcs of NAPA 500 MG (0 stock) sold, #SALE_20261027_08 Paid Tk 2 (round-off -0.40); product stock then shows -2 pcs / -0 box.", "", "", "Cost and profit 'Pending' (OBS-SALE-017)."),
    "TC-SALE-SC-15": ("Allow Loss Sale ON: TEST PRODUCT 2 pcs at Tk 6 (cost 7.32) completed as #SALE_20261027_09, profit Tk -2.64.", "", "", "Audit entry for the loss sale not checked."),
    "TC-SALE-SC-18": ("Stock shown as '0 pcs / 0 box' in the dropdown and a Stock column in the cart.", "", "", "Same display when OFF: BUG-SALE-002."),
    "TC-SALE-SC-20": ("Company 'BEXIMCO PHARMACEUTICALS LTD.' shown in the dropdown and cart.", "", "", "Same display when OFF: BUG-SALE-003."),
    "TC-SALE-SC-22": ("Profit Margin ON: checkout showed 'Approximate Profit Tk -2.64' for 12 - 14.64; the line disappears when OFF.", "", "", ""),
    "TC-SALE-SC-23": ("Rack Number ON: a 'Rack No' column appears in the cart (value '-' for the product).", "", "", "Rack value display not verified (product has no rack)."),
    "TC-SALE-SC-25": ("Separate Cashier ON: Complete Sale toasted 'Sale Complete'; the sale appeared in /cashier (Waiting in Queue 1) and in Sale Record as Paid with profit and counted in Total Collected.", "BUG-SALE-021", "", "Treasury/stock before approval not measured."),
    "TC-SALE-SC-26": ("Out of Stock, Loss, Stock Qty, Company, Profit Margin and Rack ON together: search, cart, checkout and two sales worked without errors.", "", "", "Other combinations not run."),
    "TC-SALE-CA-01": ("Queue count 1, 'Sent by Training Client', Tk 100.00, 1 item; but the sale was already Paid in Sale Record.", "BUG-SALE-021", "", ""),
    "TC-SALE-CA-02": ("Cashier Complete Sale: toast 'SALE_20261027_10 has been checked out successfully'; queue 0; no duplicate row in Sale Record (10 rows).", "", "", "Voucher/receipt and stock not verified."),
    "TC-SALE-CA-11": ("Before approval Sale Record listed the sale as Paid and the tiles included it.", "BUG-SALE-021", "", ""),
})

ACTUAL.update({
    "TC-SALE-SC-14": ("Price 7.32 (= FEFO cost) completed as #SALE_20261027_14 (Tk 15 after round-off, profit Tk 0.36); 7.31 blocked with 'below cost is not allowed'.", "", "", ""),
    "TC-SALE-SC-16": ("Allow Loss Sale OFF: Tk 10 less 40 % line discount (net 6 < cost 7.32) completed as #SALE_20261027_15, bill Tk 12, profit Tk -2.64.", "BUG-SALE-023", "", "2026-10-29 automated re-check: a 10 % line discount to net 4.50 (below cost) WAS blocked (400 'below cost'), so the bug may depend on the discount size; re-check the 40 % case by hand."),
    "TC-SALE-CK-04": ("Discount Tk 10 on Tk 100 -> Discount Amount Tk 10.00, Final Tk 90, Paid 90; sale #SALE_20261027_11 shows '-Tk 10 disc', Tk 90.", "", "", ""),
    "TC-SALE-CK-05": ("Tk 101 on a Tk 100 bill: 'Discount Amount Tk 101.00', Final Tk 0, no message; -1 ignored silently.", "BUG-SALE-024", "", "100 (= total) gives Final 0."),
    "TC-SALE-CK-15": ("Paid -5 ignored (Total Paid 100); 12.345 -> Paid 12.35 and Due 87.66; 1e9 accepted; text/blank -> Paid 0; no messages.", "BUG-SALE-024", "", ""),
    "TC-SALE-CK-18": ("Cash Received 120 on Final 90 -> Return Amount Tk 30.00; 90 / 50 / -10 -> Tk 0.00; saved sale #11 Paid Tk 90 (no advance).", "", "", ""),
    "TC-SALE-CK-19": ("'QA Walk-in 017' accepted in Walk in Customer Detail.", "", "", "Invalid phone not run."),
    "TC-SALE-CK-25": ("Double-click Complete Sale created #SALE_20261027_12 and #SALE_20261027_13 (both Tk 50, 04:25 pm).", "BUG-SALE-022", "", ""),
    "TC-SALE-CK-27": ("Reload of /sale-checkout kept the cart; browser Back returned to /sale with the cart intact.", "", "", ""),
    "TC-SALE-CK-28": ("/sale-checkout with an empty cart shows 'Cart is Empty - There is nothing to ...'.", "", "", ""),
    "TC-SALE-CK-30": ("Note textarea stops at 150 characters (counter 150/150).", "", "", "0 / 1 / 151 not run separately."),
    "TC-SALE-HS-04": ("Held sale 1 (1 pc, Tk 50), sold another sale, then resumed hold 1: cart restored with 1 pc Tk 50.", "", "", ""),
    "TC-SALE-HS-06": ("Delete icon -> 'Delete this held sale? ... Keep it / Yes, delete'; Keep it left 2; Yes, delete -> 1.", "", "", ""),
    "TC-SALE-HS-07": ("Two holds listed (Hold Id 1 and 2, time, items, Tk) with 'Total Hold List 2' and 'Clear all'.", "", "", "Three holds not run."),
})

ACTUAL.update({
    "TC-SALE-SC-03": ('Toggled Stock Qty, pressed Cancel: toggle back OFF, no PUT sent, page stays.', '', '', ''),
    "TC-SALE-SC-04": ('Toggled a switch, navigated to Loyalty Config and back: change not saved, no warning dialog.', '', '', 'No unsaved-changes prompt.'),
    "TC-SALE-SC-05": ('Double-click Save Changes: two PUT requests and two success toasts.', 'BUG-SALE-031', '', ''),
    "TC-SALE-SC-07": ('Kiayada Schmidt Pharmacy: 0 customers and its own empty loyalty page; Manik Pharma: 4 customers, loyalty 100/10/5/20.', '', '', 'Both configs were at defaults, so only customers/loyalty prove the scope.'),
    "TC-SALE-SC-08": ('Business Type Wholesale saved (PUT businessType WHOLESALE); POS default unit became Box; restored to Retail and verified after reload.', '', '', ''),
    "TC-SALE-LC-02": ('100 / 10 / 50 / 500 saved (PUT payload as typed) and shown after reload.', '', '', ''),
    "TC-SALE-LC-03": ('All values 0 saved with the success toast (program off).', 'BUG-SALE-058', '', 'Answer 4: Earning 0 is fine, Redemption 0 must be rejected; Apply-disabled state at POS not yet verified.'),
    "TC-SALE-LC-04": ("-5 and -1 sent as 0 / 0 with a success toast; 'abc' -> 'Earning Rule is required'; 2.5 saved; 1e9 typed accepted in the box.", 'BUG-SALE-025', '', ''),
    "TC-SALE-LC-05": ("Min 600 / Max 500: request sent, server answered 'Minimum redeem point must not be greater than maximum redeem point'.", '', '', ''),
    "TC-SALE-LC-06": ('Typed 7, pressed Cancel: previous values shown.', '', '', ''),
    "TC-SALE-CU-04": ('QA Due Cust: address, Due Tk 500, discount 5 %, due date 2026-10-20 created; list shows Due Tk 500; tiles Due (1) Tk 500 after reload.', '', '', 'Past due date accepted (BUG-SALE-036).'),
    "TC-SALE-CU-07": ("Same phone 1700000003 -> 'Customer already exist with phoneNumber : +8801700000003'; 01521503629 -> same error for Manik Hossain.", '', '', ''),
    "TC-SALE-CU-08": ("Spaces only -> 'Customer name must not be blank'; 300 chars -> 'must not exceed 255 characters'; Bangla name created; '<img onerror>' name stored and rendered as text.", '', '', ''),
    "TC-SALE-CU-10": ("Due 500 created from the form; Advance 300 created through Add Payment on a zero-balance customer (preview 'After this payment Advance Tk 300').", '', '', 'Negative opening balance not run.'),
    "TC-SALE-CU-11": ('Due Payment Date 2026-10-20 (past) saved without any message.', 'BUG-SALE-036', '', ''),
    "TC-SALE-CU-12": ("After Cancel and reopen the drawer still showed 'Leak Check' / 1700000008.", 'BUG-SALE-027', '', ''),
    "TC-SALE-CU-13": ("Double-click Confirm sent 2 create requests: one customer created, second returned 'already exist' toast.", '', '', ''),
    "TC-SALE-CU-16": ("11 customers: page 1 shows 'Showing 1-10 of 11', Next shows 11-11, Previous returns; sizes 10/20/50/100.", '', '', 'Go to not run.'),
    "TC-SALE-CU-17": ("Edit: name 'QA Edited One', discount 7, Active off saved (PUT customers/update); list shows Inactive; editing QA Due Cust left Due at Tk 400.", '', '', ''),
    "TC-SALE-CU-19": ('Payment 300 on a customer with balance 0: preview Advance Tk 300 and POST customer-payments/create accepted.', '', '', 'Resulting balance row not re-read.'),
    "TC-SALE-CU-22": ('Bad Debts Tk 100 with CASH and no note saved; customer Due 500 -> 400 (Dashboard Customer Due Tk 400).', 'BUG-SALE-028', '', ''),
    "TC-SALE-CU-23": ("Not executed: activating loyalty on a customer sends an SMS OTP to that customer's phone.", '', '', 'Manik Hossain was already activated by the tester.'),
    "TC-SALE-CU-24": ('After the full return of #18 the row still reads 6 orders / Tk 14,394 and 80 points.', 'BUG-SALE-026', '', ''),
    "TC-SALE-CU-25": ('Row menu: View Details, Customer Ledger, Payment History, Edit (no Delete). Edit > Active off deactivated a customer.', '', '', 'Customer with history not deactivated.'),
    "TC-SALE-PC-03": ("'estradiol' lists products by generic (ANGELA, CEPTIVA, CLEO 35 ...) and TEST PRODUCT; 'oral powder' lists by dosage form.", '', '', ''),
    "TC-SALE-PC-14": ('TEST PRODUCT 2 pc 10 % then 1 pc: one line, Qty 1, Tk 50.', 'BUG-SALE-035', '', ''),
    "TC-SALE-PC-15": ('Edit icon loads qty/price into the form with a Save Changes button; Qty 3 saved, line Tk 150.', '', '', ''),
    "TC-SALE-PC-17": ('3-C 2 x 35 + 3 BION 1.50 + 100% 40 + TEST 50 = Total Price Tk 161.50, Cart Items 4.', '', '', ''),
    "TC-SALE-PC-19": ('Second tab showed the same server cart; item added there appears in tab 1 after reload (no live sync).', '', '', ''),
    "TC-SALE-PC-22": ('3-C (expiry 1 Jan 1970) sold: #SALE_20261027_21, no warning.', 'BUG-SALE-030', '', ''),
    "TC-SALE-PC-23": ('Tab order from Product: Qty, Unit, Price, Discount, Discount type, Add to Cart.', '', '', ''),
    "TC-SALE-PC-24": ('390 px: Sale Mode wraps one letter per line, cart crushed; 768 and 1920 px have no horizontal overflow.', 'BUG-SALE-032', '.playwright-mcp/pos-mobile.png', ''),
    "TC-SALE-CK-07": ('161.50 - 16.15 = 145.35 -> Round Off -0.35 -> 145.00; 161.50 -> Round Off +0.50 -> 162.00; 2.40 -> 2.00.', '', '', ''),
    "TC-SALE-CK-08": ('Total 161.50, overall 10 % = 16.15, round -0.35, Final Tk 145.00.', '', '', 'Loyalty term not combined.'),
    "TC-SALE-CK-14": ("Walk-in, paid 0 on Tk 190: 'Payment Shortfall - Settlement Choice' with Less & Sale / Discount for the whole Tk 190.", '', '', 'Completion not run.'),
    "TC-SALE-CK-17": ("Card commission 2 %: 'Card Commission Tk 3.98', Final 145 -> 149, Total Paid 199.", '', '', '3.98 = 2 % grossed up on the card amount; confirm intended base.'),
    "TC-SALE-CK-22": ('QA Due Cust (5 %) selected: Discount box empty.', 'BUG-SALE-029', '', ''),
    "TC-SALE-CK-23": ("Add New Customer on checkout: 'QA Inline Cust' created and selected automatically.", '', '', ''),
    "TC-SALE-CK-24": ('Quick Print ticked (remembered between visits): sale completed and a print iframe was created.', '', '', 'Printed output not verified.'),
    "TC-SALE-CK-26": ("POST /sales/... aborted: toast 'Network Error', checkout kept, Complete Sale re-enabled, no sale created.", '', '', ''),
    "TC-SALE-CK-29": ('Two tenders 145 + 50 on a Tk 145 bill: Total Paid 195 and the Excess Payment dialog on Complete.', '', '', ''),
    "TC-SALE-LY-01": ('Manik Hossain bought Tk 1,050 (earning 100 Tk = 1 pt): points 0 -> 10; Tk 5,000 -> +50; Tk 8,000 -> +80.', '', '', ''),
    "TC-SALE-LY-02": ('A walk-in checkout shows no loyalty block.', '', '', ''),
    "TC-SALE-LY-04": ("60 points -> OTP SMS -> Verified -> 'Loyalty Discount Tk 6.00, 60 points applied', Final 194; after the sale points 0.", '', '', 'Redemption sale earned no point on Tk 194.'),
    "TC-SALE-LY-05": ("Wrong code 000000 -> 400 'Invalid OTP. Please try again.'; Resend code sent a new SMS.", '', '', '3-minute expiry not run; Undo then Apply again sends another SMS.'),
    "TC-SALE-LY-06": ("10 points (min 50): no Apply button; 60 points: 'Apply Max Loyalty Points' shown.", '', '', 'No explanatory message.'),
    "TC-SALE-LY-07": ('Max 20 / min 5: 80 points available, Apply Max applied only 20 points = Tk 2.00 (60 available after).', '', '', ''),
    "TC-SALE-LY-08": ('No manual points input exists (Apply Max only).', '', '', ''),
    "TC-SALE-LY-10": ('After the full return of the redeemed sale the 60 redeemed points were not restored (80 points) and Total Spent was unchanged.', 'BUG-SALE-026', '', ''),
    "TC-SALE-LY-11": ('No audit/security log screen is exposed in the UI.', '', '', ''),
    "TC-SALE-CA-02": ("Cashier Complete Sale: 'SALE_20261027_10 has been checked out successfully'; queue 0; no duplicate row.", '', '', ''),
    "TC-SALE-CA-03": ('Cashier set Discount 10 % on #25 (panel Final Tk 90) and completed; Sale Record shows Bill Tk 100, Paid Tk 100, no discount.', 'BUG-SALE-034', '', ''),
    "TC-SALE-CA-04": ("Complete all -> confirmation -> 'Queue Cleared - 3 sales have been checked out successfully', queue 0.", '', '', ''),
    "TC-SALE-CA-05": ('Search 26, SALE_20261027_26, Training, walk, CA-A all returned 0 results (also the exact invoice number of the open sale).', 'BUG-SALE-018', '', ''),
    "TC-SALE-CA-06": ('The queue has only Complete Sale and Complete all; no reject / cancel.', 'BUG-SALE-060', '', 'Answer 9: the queue should offer reject / cancel.'),
    "TC-SALE-CA-07": ('TEST PRODUCT stock 1,08,110 -> 1,08,108 after a 2-pc pending sale.', '', '', ''),
    "TC-SALE-CA-10": ('Separate Cashier switched OFF with 3 pending sales: queue still showed 3 and Complete Sale / Complete all worked.', '', '', ''),
    "TC-SALE-RT-02": ("Sale Return search: 20261027_16 and 'Manik' list registered-customer sales; SALE_20261027_15 and 'walk' -> 'No data'.", 'BUG-SALE-018', '', ''),
    "TC-SALE-RT-04": ("Full return of #18 (4 of 4 pcs): 'Return to Customer Tk 194' = amount paid; return #20 created; refund credited as Advance (5 -> 199).", '', '', 'Per-batch stock not checked.'),
    "TC-SALE-RT-16": ("Double-click Complete Sale Return: 2 POSTs, one return (#20), toast 'Return of 4 for TEST PRODUCT exceeds the remaining 0 on this line.'", '', '', 'OBS-SALE-022.'),
    "TC-SALE-DB-06": ('Yesterday Sales Tk 0; Today / 7 / 30 days Tk 14,955; More ranges: This month ... All time; Compare shows no extra figures.', '', '', ''),
    "TC-SALE-DB-09": ('Quick Links Sale, Inventory, Sale Return, Cash Closer point to /sale, /inventory, /sale-return, /accounts/cash-closer.', '', '', ''),
    "TC-SALE-NF-07": ('A customer name containing an img onerror tag was listed as plain text; window.__xss stayed undefined.', '', '', 'Checkout and Sale Record rendering not checked.'),
    "TC-SALE-NF-11": ('7 visible controls without accessible name (segmented radios, unit select).', 'BUG-SALE-033', '', ''),
})

ACTUAL.update({
    "TC-SALE-HS-08": ('Hold Current Sale on the checkout screen returned to /sale with one hold (2 items, Tk 160); resume and checkout showed the overall 10 % discount again.', '', '', 'Customer retention not tested (walk-in).'),
    "TC-SALE-CK-06": ('3-C 2 x 35 + TEST PRODUCT 2 x 50 (10 % line): overall 10 % gave Discount Amount Tk 16.00 (on 160) and Final Tk 144.', 'BUG-SALE-037', '', ''),
    "TC-SALE-IV-04": ('1 box of TEST PRODUCT (Tk 500): stock 1,08,101 pcs -> 1,08,091 pcs (10,810.1 -> 10,809.1 box).', '', '', ''),
    "TC-SALE-IV-06": ("NAPA 2 pcs from 0 stock: stock -2; cost/profit 'Pending'.", 'BUG-SALE-041', '', ''),
    "TC-SALE-IV-08": ('Return preview of #27: TEST PRODUCT 2 pcs Tk 81, 3-C 2 pcs Tk 63 = 144.', '', '', ''),
    "TC-SALE-IV-10": ('The overall discount was applied to the line-discounted item as well.', 'BUG-SALE-037', '', ''),
    "TC-SALE-IV-12": ('Two tabs clicking Complete Sale together on one cart: two 201 responses.', 'BUG-SALE-022', '', ''),
    "TC-SALE-IV-02": ('3BIOTIC 100GM: batch 2 (later expiry, Tk 240/box) bought first, batch 1 (earlier expiry, Tk 120/box) second; selling 1 pc was costed at batch 1 per-piece cost.', '', '', 'Automated: tests/sale/test_fefo_batches.py::test_sale_takes_earliest_expiry_batch (PASSED 2026-10-29).'),
    "TC-SALE-IV-03": ('Batches of 1 pc each (Tk 120 and Tk 240); selling 2 pcs took 1 pc from each batch.', '', '', 'Automated: tests/sale/test_fefo_batches.py::test_sale_spills_into_next_batch (PASSED 2026-10-29). Cost per batch is checked as the line total.'),
    "TC-SALE-IV-07": ('Out of Stock Sale ON, both batches in stock, sold 2 pcs more than all stock: Sale Details Cost shows Pending for the line instead of batch cost plus fallback cost.', 'BUG-SALE-041', '', 'Automated: tests/sale/test_fefo_batches.py::test_oversell_is_costed (FAILED on the bug, 2026-10-29).'),
    "TC-SALE-IV-14": ('Not run: needs Stock Adjust / purchase set-up.', '', '', ''),
    "TC-SALE-PC-21": ('Sampled ACI products (6) all had a sale price.', '', '', ''),
    "TC-SALE-LY-03": ("QA Due Cust (loyalty off) bought 3 pcs Tk 150: points '-', orders 1, spent Tk 150.", '', '', ''),
    "TC-SALE-SR-07": ("Edit Sale: qty 2 -> 1, Profit & Sale on the excess: 'Sale has been updated successfully'; row bill Tk 50, paid Tk 100, status Advance; Change History has 2 entries.", '', '', 'Status Advance for a walk-in: BUG-SALE-008.'),
    "TC-SALE-SR-08": ("Edit price to Tk 5: 'Selling TEST PRODUCT below cost is not allowed for this pharmacy'; edit of #27 (has a return): 'Sale SALE_20261027_27 is not editable'.", '', '', 'Qty 0 not run.'),
    "TC-SALE-SR-11": ("Cancel Sale on #27 (1 pc already returned) -> 'Sale has been canceled successfully', status Cancelled.", 'BUG-SALE-039', '', ''),
    "TC-SALE-SR-13": ('Not run: Cash Closer saves itself on opening.', '', '', 'OBS-SALE-011.'),
    "TC-SALE-SR-14": ('Print Receipt created a blob PDF (application/pdf, 204 x 278 pt).', '', '', 'PDF text not asserted.'),
    "TC-SALE-SR-16": ('Invoice Config (top/bottom text, Served By, Customer Name) saved then restored; receipt PDF fonts are embedded so the text was not read.', '', '', ''),
    "TC-SALE-RT-08": ('Line-discounted TEST PRODUCT: 1 pc Return Price Tk 40.50, 2 pcs Tk 81.', '', '', 'Rounding: BUG-SALE-038.'),
    "TC-SALE-NF-03": ("Replayed POST sales/create: qty -1 -> 400 'Qty must be greater than zero'; amount 0 and -10 -> 400 'Amount must be greater than zero'; tampered totalItemPrice -> recomputed (201); walk-in amount 1 of 50 -> 201 with Due Tk 49.", 'BUG-SALE-040', '', ''),
    "TC-SALE-NF-04": ('Change History shows time, action and user only.', 'BUG-SALE-042', '', ''),
    "TC-SALE-NF-05": ('12.345 -> 12.35 / 87.66; single returns of 40.50 refund 41 each.', 'BUG-SALE-038', '', ''),
    "TC-SALE-NF-06": ('Two tabs completing the same cart at once created two sales.', 'BUG-SALE-022', '', ''),
    "TC-SALE-NF-08": ('Cookies pms-token / pms-refresh-token cleared at checkout: POST -> 401, redirected to /login, no sale created.', '', '', 'No message on the login page.'),
    "TC-SALE-NF-09": ('Page ready: Dashboard 2.4 s, Sale Record (31 rows) 3.7 s, Customers 3.4 s, POS 3.4 s, product search 1.3 s.', '', '', 'Staging dev build; Firefox/WebKit cold loads took 36-40 s.'),
    "TC-SALE-NF-10": ('Firefox and WebKit: Sale Record 10 rows, POS search 5 options, add to cart, checkout total visible, no page errors.', '', '', ''),
    "TC-SALE-NF-02": ('Not run: only the Owner login is available.', '', '', ''),
    "TC-SALE-SC-09": ('Not run: needs a non-owner login.', '', '', ''),
    "TC-SALE-LC-07": ('Not run: needs a non-owner login.', '', '', ''),
    "TC-SALE-CA-08": ('Not run: needs a non-owner login.', '', '', ''),
    "TC-SALE-SR-15": ('Not run: needs a non-owner login.', '', '', ''),
})

ACTUAL.update({
    "TC-SALE-SC-28": ("Profit Margin OFF: Sale Record shows a Profit column and 'Total Profit' tile; the Cashier panel shows 'Approximate Profit Tk 85.36'; Checkout hides it.", 'BUG-SALE-043', '', ''),
    "TC-SALE-PC-26": ("TEST PRODUCT default Sale/pc Tk 6 -> per box Tk 60; typed Tk 50 per pc shows 'Sale/bx Tk 500.00'.", '', '', ''),
    "TC-SALE-CK-31": ('Summary: Total Price 170, Discount Amount 16, Round Off 0, Final 144 - the Tk 10 line discount is not shown.', 'BUG-SALE-044', '', ''),
    "TC-SALE-CK-32": ('Tender list CASH / BANK / CARD / MFS; CASH 30 + CARD 20 split completed (#SALE_20261027_07).', '', '', 'Per-tender Treasury effect not checked.'),
    "TC-SALE-CA-12": ('Cashier panel fields: Discount, Card Commission, Customer Paid + tender, Cash Received, Note; no quantity control.', 'BUG-SALE-045', '', ''),
    "TC-SALE-RT-18": ("Customer Ledger shows static demo data instead of the customer's own entries.", 'BUG-SALE-007', '', ''),
    "TC-SALE-NF-12": ('No audit / security log screen is exposed in the UI.', '', '', ''),
})

ACTUAL.update({
    "TC-SALE-SC-29": ("Rack ON: cart header gets 'Rack No' with A1; the dropdown option has no rack.", 'BUG-SALE-046', '', ''),
    "TC-SALE-PC-25": ('Business Type Wholesale: default unit Box; field wholesalePricePerBox = 50 (5 per pc x 10).', '', '', 'Restored to Retail.'),
    "TC-SALE-CA-13": ("Approve SALE_20261028_02: toast 'checked out successfully'; no print iframe, popup or Print button.", 'BUG-SALE-050', '', ''),
    "TC-SALE-SR-17": ("Change History drawer: only a 'Search by change date' input; an entry expands to Field Name / From / To.", '', '', 'API edit/delete not attempted.'),
    "TC-SALE-SR-18": ("Pay Due Tk 10 CASH on #04: 'Payment has been recorded successfully', drawer closes, nothing to print.", 'BUG-SALE-049', '', ''),
    "TC-SALE-RT-17": ('QA Due Cust (Due 400) returned 1 of 3 pcs (Tk 50): Return Checkout has no method options; customer Due became Tk 350.', 'BUG-SALE-059', '', 'Answer 7: the seller should choose Cash or reduce Due. Total Spent stayed Tk 150 (BUG-SALE-026).'),
    "TC-SALE-NF-04": ("Expanding the 'Edit' entry of #24 lists Field Name / From / To: Total Price Tk 100 -> 50, Final Price 100 -> 50, Settlement Type - -> PROFIT, Approximate Profit 85.70 -> 42.85.", '', '', 'Corrects the earlier BUG-SALE-042 (withdrawn).'),
    "TC-SALE-SR-04": ('Date range 2026-10-27 works (from/to in the URL); Status Paid -> 0 rows, Due -> 0 rows, Cancelled -> 2, Returned -> 1; payment method and channel options listed.', 'BUG-SALE-048', '', 'Sold By not run.'),
    "TC-SALE-SR-01": ('On 28 Oct the grid is empty (hidden default today filter) while the tiles show 33 sales.', 'BUG-SALE-047', '', ''),
})

ACTUAL.update({
    "TC-SALE-CU-06": ("9 digits and a '12...' prefix rejected; 11 and 14 digits are cut to the first 10 and saved/matched (+8801700000304); '0000000000' leaves the box empty; a space is stripped.", 'BUG-SALE-051', '', ''),
    "TC-SALE-CU-08": ("255 chars created, 256 rejected, 1 char and an emoji name created, spaces-only rejected; '   QA Trim   ' stored with its spaces (13 chars).", 'BUG-SALE-052', '', ''),
    "TC-SALE-CU-09": ("-1 -> 0, 'abc' -> empty/0, 100.01 -> 100, 0.01 and 100 kept; no messages.", '', '', 'OBS-SALE-029.'),
    "TC-SALE-CU-10": ('Advance 10.555 -> saved as 11; Advance 1e9 accepted; -50 sent as 0.', 'BUG-SALE-053', '', ''),
    "TC-SALE-CU-18": ('Double-click Confirm New Payment (Tk 5): 2 POSTs, 2 toasts, Due 350 -> 340.', 'BUG-SALE-055', '', ''),
    "TC-SALE-CK-14": ('Walk-in paid 0, Less & Sale: #SALE_20261028_05 Bill Tk 0 (-Tk 50 disc), profit Tk -7.15.', '', '', 'No cap or approval for a 100 % waiver.'),
    "TC-SALE-CK-19": ('Detail with 400 characters accepted; an HTML snippet stayed inert; the saved sale shows no detail.', '', '', 'BUG-SALE-054.'),
    "TC-SALE-CK-30": ('Note 0/1/149/150 kept, 151 cut to 150; the note is not shown in Sale Details.', 'BUG-SALE-054', '', ''),
    "TC-SALE-SR-12": ("Double-click 'Yes, cancel it' on #SALE_20261028_03: one cancel request, stock 1,08,091 -> 1,08,092.", '', '', ''),
    "TC-SALE-RT-05": ("Second return of an already returned quantity: 'Return of 4 for TEST PRODUCT exceeds the remaining 0 on this line.'", '', '', ''),
    "TC-SALE-PC-09": ('1 box of TEST PRODUCT deducted 10 pcs (1,08,101 -> 1,08,091).', '', '', ''),
    "TC-SALE-NF-07": ('img onerror / script strings in customer name, walk-in detail and note: no script ran, no dialog, no injected image.', '', '', ''),
    "TC-SALE-HS-02": ('Double-click Hold Current Sale left 2 holds for one cart (cleared afterwards with Clear all).', 'BUG-SALE-056', '', ''),
})

ACTUAL.update({
    "TC-SALE-CU-13": ('Double-click Confirm New Customer: 2 create requests; one customer created, the second rejected as a duplicate phone with an error toast.', 'BUG-SALE-057', '', 'Automated: tests/sale/test_double_submit.py.'),
    "TC-SALE-RT-16": ("Double-click Complete Sale Return: 2 POSTs, one return (#20); the second answered 'exceeds the remaining 0 on this line' and an error toast appeared.", 'BUG-SALE-057', '', 'Automated: tests/sale/test_double_submit.py.'),
})

def _status(cell: str) -> str:
    c = cell.replace("*", "").strip().lower()
    for key, val in (("fail", "Fail"), ("pass", "Pass"), ("blocked", "Blocked")):
        if c.startswith(key):
            return val
    return "Not Run"


def load(TC) -> list:
    out = []
    bug_sev = {b["Bug ID"]: b["Severity"] for b in json.loads(BUGS.read_text(encoding="utf-8"))} if BUGS.exists() else {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| TC-SALE-"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        tid, scn, steps, exp, pri, st = c[0], c[1], c[2], c[3], c[4], c[5]
        module, feature = SECTIONS[tid.split("-")[2]]
        status = _status(st)
        actual, bug, ev, rem = ACTUAL.get(tid, ("", "", "", ""))
        if status == "Blocked":
            rem = (rem + " Requirement gap - needs a product-owner answer or a missing account.").strip()
        out.append(TC(
            id=tid, module=module, feature=feature, sub=scn, scenario=scn, desc=scn + ".",
            steps=steps or "Set up the scenario as described in Test Scenario, then observe the result.", expected=exp, ttype=_type(scn, steps), priority=PRIORITY[pri],
            severity=bug_sev.get(bug, PRIORITY[pri]) if status == "Fail" else "", status=status, actual=actual,
            data=DATA, precond=PRECOND, evidence=ev, bug=bug, remarks=rem,
        ))
    return out
