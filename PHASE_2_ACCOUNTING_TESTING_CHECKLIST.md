# Phase 2 Accounting Integration — Manual Testing Checklist

## Prerequisites

Before running any test:
- [ ] `bench migrate` completed without errors
- [ ] `bench clear-cache` and `bench clear-website-cache` executed
- [ ] Cheque Settings configured with all six account fields
- [ ] At least one Customer and one Supplier exist
- [ ] At least one Cash/Bank account exists per company
- [ ] Company has `exchange_gain_loss_account` configured (for multi-currency tests)

---

## Part 1 — Customer Receipt

### 1.1 Cash only receipt
- [ ] Create Cheque Customer Receipt, payment_mode = Cash
- [ ] Enter cash_account and cash_amount > 0
- [ ] Submit
- [ ] Verify: Payment Entry created with type = Receive
- [ ] Verify: Payment Entry links back to receipt
- [ ] Verify: Customer receivable balance reduced
- [ ] Verify: Cash account balance increased

### 1.2 Cheque only receipt
- [ ] Create Cheque Customer Receipt, payment_mode = Cheque
- [ ] Add one cheque row (cheque_no, bank, due_date, currency, amount, exchange_rate)
- [ ] Submit
- [ ] Verify: Cheque Register created automatically (cheque_type = Incoming, status = Received / In Hand)
- [ ] Verify: Journal Entry created: Dr Cheques In Hand / Cr Customer Receivable
- [ ] Verify: JE linked on cheque row and on Cheque Register (linked_journal_entry)
- [ ] Verify: Cheque Register has customer_receipt link pointing to receipt

### 1.3 Cash + multiple cheques receipt
- [ ] Create Cheque Customer Receipt, payment_mode = Cash + Cheque
- [ ] Enter cash_amount > 0 and add 2+ cheque rows
- [ ] Submit
- [ ] Verify: Payment Entry created for cash
- [ ] Verify: One Cheque Register created per cheque row
- [ ] Verify: One Journal Entry created per cheque row
- [ ] Verify: total_received_amount = cash_amount + sum of cheque amounts
- [ ] Verify: All link fields populated correctly

### 1.4 Foreign currency cheque receipt
- [ ] Add cheque row with currency ≠ company currency
- [ ] Set exchange_rate > 1
- [ ] Submit
- [ ] Verify: base_amount = amount × exchange_rate on child row
- [ ] Verify: Cheque Register has correct exchange_rate and base_amount
- [ ] Verify: Journal Entry amounts are correct

### 1.5 Duplicate cheque number prevention
- [ ] Add two cheque rows with the same cheque_no
- [ ] Verify: Validation error before submit

### 1.6 Cancel receipt — cheque has no later movements
- [ ] Submit a receipt with one cheque row
- [ ] Cancel the receipt immediately
- [ ] Verify: Cheque Register is cancelled
- [ ] Verify: Journal Entry is cancelled
- [ ] Verify: Payment Entry (if any) is cancelled
- [ ] Verify: Customer balance restored

### 1.7 Cancel receipt — cheque has later movements (should be blocked)
- [ ] Submit a receipt with one cheque row
- [ ] On the Cheque Register, run "Deposit to Bank"
- [ ] Try to cancel the receipt
- [ ] Verify: Clear error message blocking cancellation
- [ ] Verify: Receipt and all documents remain intact

### 1.8 Missing required fields
- [ ] Try submitting without company → error
- [ ] Try submitting without customer → error
- [ ] Try submitting in Cash mode without cash_account → error
- [ ] Try submitting in Cheque mode without cheque rows → error
- [ ] Try submitting cheque row without cheque_no → error

---

## Part 2 — Incoming Cheque Lifecycle Accounting

For each test, start with a submitted Cheque Customer Receipt to create the Cheque Register.

### 2.1 Deposit to Bank
- [ ] On a "Received / In Hand" cheque, click Deposit to Bank
- [ ] Verify: Cheque Movement created with movement_type = Deposit to Bank
- [ ] Verify: Journal Entry: Dr Cheques Under Collection / Cr Cheques In Hand
- [ ] Verify: Cheque status = Deposited / Under Collection
- [ ] Verify: Cheque Movement has journal_entry and accounting_posted = 1

### 2.2 Mark as Cleared (same currency)
- [ ] On a "Deposited / Under Collection" cheque, click Mark as Cleared
- [ ] Verify: JE: Dr Bank Account / Cr Cheques Under Collection
- [ ] Verify: Cheque status = Cleared

### 2.3 Mark as Cleared (foreign currency, exchange gain)
- [ ] Use a foreign currency cheque deposited to bank
- [ ] Clear with movement_exchange_rate > original_exchange_rate
- [ ] Verify: JE has three rows: Dr Bank / Cr Under Collection / Cr Exchange Gain

### 2.4 Mark as Cleared (foreign currency, exchange loss)
- [ ] Clear with movement_exchange_rate < original_exchange_rate
- [ ] Verify: JE has three rows: Dr Bank / Dr Exchange Loss / Cr Under Collection

### 2.5 Mark as Returned from Under Collection
- [ ] Deposit a cheque, then mark as returned
- [ ] Verify: JE: Dr Customer Receivable / Cr Cheques Under Collection
- [ ] Verify: Customer balance restored (receivable increased)
- [ ] Verify: Cheque status = Returned

### 2.6 Mark as Returned from In Hand (direct return)
- [ ] On "Received / In Hand" cheque, mark as returned
- [ ] Verify: JE: Dr Customer Receivable / Cr Cheques In Hand
- [ ] Verify: Cheque status = Returned

### 2.7 Return to Customer (physical handback)
- [ ] On "Returned" cheque, run Return to Customer
- [ ] Verify: Cheque Movement created
- [ ] Verify: No Journal Entry created (physical handback only)
- [ ] Verify: Cheque status = Returned to Customer

### 2.8 Endorse to Supplier (same currency)
- [ ] On "Received / In Hand" cheque, click Endorse to Supplier
- [ ] Select a supplier
- [ ] Verify: JE: Dr Supplier Payable / Cr Cheques In Hand
- [ ] Verify: Cheque status = Endorsed to Supplier
- [ ] Verify: endorsed_to_supplier field set on Cheque Register

### 2.9 Endorse to Supplier (foreign currency exchange difference)
- [ ] Use foreign currency cheque, endorse with different movement_exchange_rate
- [ ] Verify: JE has exchange gain/loss row

### 2.10 Mark as Returned from Endorsed to Supplier
- [ ] Endorse a cheque, then mark as returned (from Endorsed status)
- [ ] Verify: JE: Dr Customer Receivable / Cr Supplier Payable
- [ ] Verify: Cheque status = Returned

### 2.11 Cancel from In Hand
- [ ] On "Received / In Hand" cheque, run Cancel Cheque
- [ ] Verify: JE: Dr Customer Receivable / Cr Cheques In Hand
- [ ] Verify: Cheque status = Cancelled

### 2.12 Cancel from Under Collection
- [ ] Deposit cheque, then cancel
- [ ] Verify: JE: Dr Customer Receivable / Cr Cheques Under Collection
- [ ] Verify: Cheque status = Cancelled

### 2.13 Cancel from Endorsed
- [ ] Endorse cheque, then cancel
- [ ] Verify: JE: Dr Customer Receivable / Cr Supplier Payable
- [ ] Verify: Cheque status = Cancelled

### 2.14 Cancel from Returned (no accounting expected)
- [ ] Return a cheque (from hand or collection), then cancel
- [ ] Verify: No Journal Entry created (customer receivable already restored)
- [ ] Verify: Cheque status = Cancelled

### 2.15 Cancel a Movement (reversal)
- [ ] Deposit a cheque, then cancel the Deposit movement
- [ ] Verify: Deposit JE is cancelled (GL reversed)
- [ ] Verify: Cheque status restored to Received / In Hand
- [ ] Verify: accounting_posted reset to 0 on movement

---

## Part 3 — Supplier Payment

### 3.1 Cash only supplier payment
- [ ] Create Cheque Supplier Payment, payment_mode = Cash
- [ ] Submit
- [ ] Verify: Payment Entry type = Pay, from cash_account, to supplier payable
- [ ] Verify: Supplier balance reduced

### 3.2 Cheque only supplier payment (endorse existing cheque)
- [ ] Create Cheque Supplier Payment, payment_mode = Cheque
- [ ] Select an available cheque (status = Received / In Hand)
- [ ] Submit
- [ ] Verify: Cheque Movement created (Endorse to Supplier)
- [ ] Verify: JE: Dr Supplier Payable / Cr Cheques In Hand
- [ ] Verify: Cheque status = Endorsed to Supplier
- [ ] Verify: Cheque Register has supplier_payment link
- [ ] Verify: Child row has movement and journal_entry filled

### 3.3 Cash + cheque supplier payment
- [ ] Use both cash_amount and selected cheques
- [ ] Submit
- [ ] Verify: Payment Entry for cash, Movement + JE for each cheque

### 3.4 Multiple cheques to one supplier
- [ ] Select 2+ available cheques in the child table
- [ ] Submit
- [ ] Verify: One movement per cheque, one JE per cheque

### 3.5 Prevent using already-used cheque
- [ ] Submit a Supplier Payment using cheque A
- [ ] Create another Supplier Payment and try to use cheque A
- [ ] Verify: Error at submit time blocking duplicate use

### 3.6 Prevent using collected cheque
- [ ] Deposit a cheque (status = Deposited / Under Collection)
- [ ] Try to add it to Cheque Supplier Payment child table
- [ ] Verify: Link filter excludes it (only Received / In Hand shown)

### 3.7 Prevent using returned cheque
- [ ] Return a cheque
- [ ] Verify: Not available in Cheque Supplier Payment link filter

### 3.8 Prevent using cancelled cheque
- [ ] Cancel a cheque
- [ ] Verify: Not available in Cheque Supplier Payment link filter

### 3.9 Prevent duplicate cheque in same payment
- [ ] Add the same cheque register twice in the child table
- [ ] Verify: Validation error before submit

### 3.10 Cancel Supplier Payment (cash only)
- [ ] Submit and then cancel a cash-only Supplier Payment
- [ ] Verify: Payment Entry cancelled
- [ ] Verify: Supplier balance restored

### 3.11 Cancel Supplier Payment (cheque endorsement)
- [ ] Submit a Supplier Payment with one endorsed cheque
- [ ] Cancel the Supplier Payment
- [ ] Verify: Cheque Movement cancelled
- [ ] Verify: JE for endorsement cancelled
- [ ] Verify: Cheque status restored to Received / In Hand
- [ ] Verify: Cheque is available again for another payment

---

## Part 4 — Outgoing Company Cheque

### 4.1 Issue company cheque to supplier
- [ ] Create Company Cheque Issue, party_type = Supplier
- [ ] Submit
- [ ] Verify: Cheque Register created (cheque_type = Outgoing, status = Issued)
- [ ] Verify: JE: Dr Supplier Payable / Cr Post Dated Cheques Payable
- [ ] Verify: Cheque Register has company_cheque_issue link
- [ ] Verify: Company Cheque Issue has cheque_register and journal_entry links

### 4.2 Issue company cheque to customer (refund)
- [ ] Create Company Cheque Issue, party_type = Customer
- [ ] Submit
- [ ] Verify: JE: Dr Customer Receivable / Cr Post Dated Cheques Payable

### 4.3 Clear outgoing cheque from bank
- [ ] On a "Issued" outgoing Cheque Register, click Mark as Cleared
- [ ] Select bank account, posting date
- [ ] Submit movement
- [ ] Verify: JE: Dr Post Dated Cheques Payable / Cr Bank Account
- [ ] Verify: Cheque status = Cleared
- [ ] Verify: Company Cheque Issue status remains Issued (historical record)

### 4.4 Clear outgoing cheque with exchange difference
- [ ] Use a foreign currency outgoing cheque
- [ ] Clear with movement_exchange_rate ≠ original
- [ ] Verify: JE has exchange gain/loss row

### 4.5 Cancel outgoing cheque before clearing (via Company Cheque Issue)
- [ ] Submit Company Cheque Issue (status = Issued, no movements)
- [ ] Cancel the Company Cheque Issue
- [ ] Verify: Issuance JE is cancelled (GL reversed, docstatus = 2)
- [ ] Verify: Cheque Register is directly cancelled (not via Cancel movement)
- [ ] Verify: No extra reversal Journal Entry created
- [ ] Verify: Company Cheque Issue status = Cancelled

### 4.6 Prevent cancel after clearing
- [ ] Submit Company Cheque Issue, clear the cheque via movement
- [ ] Try to cancel the Company Cheque Issue
- [ ] Verify: Clear error message: "Cheque has already been cleared"

### 4.7 Prevent cancel when movements exist (other than cleared)
- [ ] Submit Company Cheque Issue, then cancel the outgoing cheque via Cheque Movement
- [ ] Do NOT cancel the movement first
- [ ] Try to cancel the Company Cheque Issue directly
- [ ] Verify: Clear error message: "Cancel the latest movement first"

### 4.8 Duplicate cheque number prevention for outgoing
- [ ] Submit a Company Cheque Issue with cheque number "001"
- [ ] Try to create another with the same number and same company
- [ ] Verify: Error before submit

---

## Part 5 — Accounting Verification

### 5.1 Customer balance verification
- [ ] Note customer outstanding before any receipt
- [ ] Submit receipt with cash + 2 cheques
- [ ] Verify: Outstanding reduced by total_received_amount
- [ ] Cancel receipt
- [ ] Verify: Outstanding restored to original value

### 5.2 Supplier balance verification
- [ ] Note supplier outstanding before payment
- [ ] Submit supplier payment with cash + endorsed cheque
- [ ] Verify: Outstanding reduced by total_paid_amount
- [ ] Cancel payment
- [ ] Verify: Outstanding restored

### 5.3 Cheques In Hand account balance
- [ ] Note account balance before receipt
- [ ] Submit receipt with cheque
- [ ] Verify: Balance increased by cheque amount
- [ ] Deposit cheque to bank
- [ ] Verify: Balance back to original (moved to Under Collection)

### 5.4 Cheques Under Collection account balance
- [ ] Deposit cheque → Under Collection balance increases
- [ ] Clear cheque → Under Collection balance decreases, Bank increases

### 5.5 Post Dated Cheques Payable account
- [ ] Issue outgoing cheque → Post Dated Cheques Payable increases
- [ ] Clear outgoing cheque → Post Dated Cheques Payable decreases, Bank decreases

### 5.6 Exchange gain/loss verification
- [ ] Create foreign currency cheque, clear with gain
- [ ] Verify: Exchange Gain/Loss account has credit entry
- [ ] Check GL entries in Journal Entry

---

## Part 6 — UI / Client Script

### 6.1 Payment mode toggles correct fields
- [ ] In Cheque Customer Receipt, change payment_mode to Cash → cheque table hidden
- [ ] Change to Cheque → cash fields hidden
- [ ] Change to Cash + Cheque → both visible

### 6.2 Totals recalculate on change
- [ ] Enter cash_amount → total_received_amount updates
- [ ] Add cheque row with amount → cheque_amount and total update
- [ ] Remove cheque row → total updates

### 6.3 Supplier payment cheque link filter
- [ ] In Cheque Supplier Payment child table, open cheque_register link
- [ ] Verify: Only Incoming, Received / In Hand, same company cheques shown
- [ ] Verify: Already-endorsed cheques are not shown

### 6.4 Cheque details auto-fill in Supplier Payment
- [ ] Select a cheque_register in child row
- [ ] Verify: cheque_no, original_customer, bank, due_date, amount, currency, exchange_rate auto-filled

### 6.5 Company Cheque Issue base amount
- [ ] Enter amount and exchange_rate in Company Cheque Issue
- [ ] Verify: base_amount = amount × exchange_rate (calculated in JS)

### 6.6 No browser console errors
- [ ] Open each form (Customer Receipt, Supplier Payment, Company Cheque Issue)
- [ ] Open browser dev tools console
- [ ] Verify: No JavaScript errors

### 6.7 List views load correctly
- [ ] Cheque Customer Receipt list shows: customer, posting_date, payment_mode, total_received_amount, status
- [ ] Cheque Supplier Payment list shows: supplier, posting_date, payment_mode, total_paid_amount, status
- [ ] Company Cheque Issue list shows: party, cheque_number, amount, due_date, status
- [ ] Status indicators show correct colors (green=submitted/cleared, orange=draft, red=cancelled)

---

## Part 7 — Cheque Register List View

- [ ] Cheque Register list shows: cheque_number, party, bank_name, due_date, amount, currency, current_status
- [ ] customer_receipt / supplier_payment / company_cheque_issue links visible on form
- [ ] current_movement points to latest submitted movement
- [ ] linked_journal_entry points to correct JE

---

## Part 8 — Cheque Settings Validation

- [ ] Remove cheques_receivable_in_hand_account from Cheque Settings
- [ ] Try to submit a Cheque Customer Receipt with cheque rows
- [ ] Verify: Clear error: "cheques_receivable_in_hand_account is not configured in Cheque Settings"
- [ ] Restore the account and verify submit succeeds

---

## Part 9 — Docker Build and Smoke Test

```powershell
# From evox-erp-infra:
.\scripts\windows\build-custom-image.ps1
.\scripts\windows\start-local-production.ps1 -ForceRecreate

# Then inside backend container:
bench --site evox.localhost migrate
bench --site evox.localhost clear-cache
bench --site evox.localhost clear-website-cache
```

- [ ] Migration completes without errors
- [ ] All six new DocTypes appear in Cheque Management workspace
- [ ] Can create, submit, and cancel each new DocType
- [ ] No 500 errors on any form load
- [ ] No traceback in bench logs during submit/cancel
