# Phase 1 — Cheque Management Testing Checklist

Use this checklist when testing any branch that contains Phase 1 cheque management code before merging.

**Site:** `evox.localhost`
**App:** `evox_erp`

Mark each item as Pass / Fail / N/A with notes.

---

## A. General Setup Checks

- [ ] Cheque Management workspace loads correctly in ERPNext.
- [ ] Required DocTypes are installed and appear in the workspace.
- [ ] Custom fields are visible and correctly positioned.
- [ ] Permissions work correctly for the test user role.
- [ ] No browser console errors on load.
- [ ] No server traceback in `logs/web.error.log`.
- [ ] `bench doctor` reports no critical issues.

---

## B. Customer Cheque Receiving Flow

**Action:** Create a new Cheque Register received from a customer.

Steps:
- [ ] Open Cheque Register → New.
- [ ] Select Party Type = Customer.
- [ ] Select a Customer.
- [ ] Enter cheque number.
- [ ] Enter bank name.
- [ ] Enter due date (future date).
- [ ] Enter amount.
- [ ] Select currency.
- [ ] Verify exchange rate behavior:
  - If local currency → exchange rate should be 1 or hidden/read-only.
  - If foreign currency → exchange rate should be required and editable.
- [ ] Save the document.
- [ ] Submit the document.

Expected:
- [ ] Status is correct after submit (e.g., "Received" or equivalent).
- [ ] Required fields are enforced — cannot submit without them.
- [ ] Accounting impact is correct if Phase 1 supports it.
- [ ] Linked Journal Entry or Payment Entry is created if applicable.
- [ ] No duplicate accounting entries are created.
- [ ] No traceback in server logs.

---

## C. Cheque Under Collection Flow

**Action:** Move a received cheque to Under Collection.

Steps:
- [ ] Open an existing Received cheque.
- [ ] Add a new Cheque Movement with movement type = Under Collection.
- [ ] Select bank/cash account if required.
- [ ] Set posting date.
- [ ] Submit the movement.

Expected:
- [ ] Cheque status changes to "Under Collection".
- [ ] Correct accounts are used in GL Entries.
- [ ] GL Entries are correct if applicable.
- [ ] User cannot submit an incomplete movement (missing required fields).
- [ ] No traceback.

---

## D. Cheque Collected Flow

**Action:** Mark a cheque as Collected.

Steps:
- [ ] Open a cheque in "Under Collection" state.
- [ ] Add movement type = Collected.
- [ ] Set posting date.
- [ ] Verify bank account is correct.
- [ ] Verify exchange rate for foreign currency cheques.
- [ ] Submit the movement.

Expected:
- [ ] Cheque status becomes "Collected".
- [ ] Accounting entries are correct.
- [ ] No incorrect outstanding balance remains on the party.
- [ ] Multi-currency amount is handled correctly (company currency equivalent is correct).
- [ ] No traceback.

---

## E. Returned Cheque Flow

**Action:** Return a cheque from bank or collection.

Steps:
- [ ] Open a cheque in "Under Collection" or submitted state.
- [ ] Add movement type = Returned.
- [ ] Fill in reason field if available.
- [ ] Set posting date.
- [ ] Submit the return movement.

Expected:
- [ ] Cheque status becomes "Returned".
- [ ] Accounting impact is reversed or posted correctly.
- [ ] Customer balance impact is correct (outstanding restored if applicable).
- [ ] Original references (cheque number, party, amount) remain traceable.
- [ ] No traceback.

---

## F. Endorsed / Transferred to Supplier Flow

**Action:** Transfer/endorse a customer cheque to a supplier.

Steps:
- [ ] Open a received cheque (status = Received or Under Collection).
- [ ] Add movement type = Endorsed/Transferred.
- [ ] Select Party Type = Supplier.
- [ ] Select a Supplier.
- [ ] Verify supplier account is populated.
- [ ] Submit.

Expected:
- [ ] Cheque status becomes "Endorsed" or "Transferred".
- [ ] Supplier balance impact is correct.
- [ ] Customer cheque remains traceable (original references intact).
- [ ] GL Entries are correct if supported in Phase 1.
- [ ] No traceback.

---

## G. Cancel Cheque Movement

**Action:** Cancel each type of movement where cancellation is allowed.

- [ ] Cancel a Received movement → status rolls back correctly.
- [ ] Cancel an Under Collection movement → status rolls back correctly.
- [ ] Cancel a Collected movement → status rolls back correctly.
- [ ] Cancel a Returned movement → status rolls back correctly.
- [ ] Cancel an Endorsed/Transferred movement → status rolls back correctly.

Expected for each:
- [ ] Status reverts to the previous valid state.
- [ ] Accounting entries are cancelled/reversed correctly.
- [ ] No orphan Journal Entry or Payment Entry remains.
- [ ] User cannot cancel from an invalid state (e.g., cannot cancel Collected if already returned).
- [ ] No traceback.

---

## H. Exchange Rate Tests

### H1. Local Currency Cheque
- [ ] Create a cheque where cheque currency = company currency.
- Expected: Exchange rate should be 1, or the field is hidden/read-only.

### H2. Foreign Currency Cheque
- [ ] Create a cheque where cheque currency ≠ company currency.
- Expected: Exchange rate field is required and user can enter/edit the rate.

### H3. Exchange Rate Reset on Movement Change
Steps:
- [ ] Open a Cheque Movement form.
- [ ] Select movement type = Collected.
- [ ] Enter exchange rate = 4.
- [ ] Change movement type to Returned (or another movement type).
- Expected: The old exchange rate (4) does not incorrectly persist.
- Expected: Exchange rate resets or recalculates based on movement type, date, currency, party, and company currency.
- [ ] Confirm exchange rate is appropriate for the new movement.

### H4. Read-Only Behavior
- [ ] Exchange rate is only read-only where business logic requires it.
- [ ] Exchange rate is NOT globally locked — user can adjust it for valid movements that need it.
- [ ] Read-only state matches the movement type and currency context.

---

## I. Validation Tests

- [ ] Cannot submit a cheque without a party (Customer or Supplier).
- [ ] Cannot submit a cheque without a cheque number.
- [ ] Cannot submit a cheque without an amount.
- [ ] Cannot submit a cheque without a due date.
- [ ] Cannot perform an invalid status transition (e.g., directly from Received to Collected without Under Collection if the workflow requires it).
- [ ] Cannot collect an already collected cheque.
- [ ] Cannot transfer a cancelled cheque.
- [ ] Cannot return an already cancelled cheque.
- [ ] Cannot create a duplicate movement for the same cheque in the same state.

---

## J. Accounting Tests

For every supported movement, verify in GL Entries:

| Check | Received | Under Collection | Collected | Returned | Endorsed |
|---|---|---|---|---|---|
| Debit account | [ ] | [ ] | [ ] | [ ] | [ ] |
| Credit account | [ ] | [ ] | [ ] | [ ] | [ ] |
| Party type | [ ] | [ ] | [ ] | [ ] | [ ] |
| Party | [ ] | [ ] | [ ] | [ ] | [ ] |
| Amount | [ ] | [ ] | [ ] | [ ] | [ ] |
| Currency | [ ] | [ ] | [ ] | [ ] | [ ] |
| Exchange rate | [ ] | [ ] | [ ] | [ ] | [ ] |
| Company currency amount | [ ] | [ ] | [ ] | [ ] | [ ] |
| Posting date | [ ] | [ ] | [ ] | [ ] | [ ] |
| Linked document | [ ] | [ ] | [ ] | [ ] | [ ] |
| Cancel/reversal | [ ] | [ ] | [ ] | [ ] | [ ] |

---

## K. Reports / List View Checks

- [ ] Cheque Register appears in the correct status in list view.
- [ ] Status filter works correctly.
- [ ] Customer/Supplier filter works correctly.
- [ ] Due date filter works correctly.
- [ ] Amount and currency display correctly in list view.
- [ ] Linked accounting document (JE or PE) is visible and clickable.
- [ ] No console errors in list view.

---

## L. Final Branch Acceptance Checklist

Before merging any branch, confirm all of the following:

- [ ] `bench migrate` passed with no errors.
- [ ] `bench build` passed with no errors.
- [ ] `bench restart` (container restart) completed.
- [ ] No errors in `logs/web.error.log`.
- [ ] No errors in `logs/worker.error.log`.
- [ ] No errors in browser console.
- [ ] Full Phase 1 checklist (A through K) passed.
- [ ] Git diff reviewed — changes are correct and expected.
- [ ] No ERPNext or Frappe core files (`apps/erpnext/`, `apps/frappe/`) were modified.
- [ ] No secrets, passwords, API keys, or `site_config.json` committed.
- [ ] Merge commit uses `--no-ff`.
