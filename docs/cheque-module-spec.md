# Cheque Module Specification

The cheque module will provide controlled cheque lifecycle management for incoming and outgoing cheques in ERPNext.

## DocTypes

### Cheque Settings

Singleton DocType:

- company
- cheques_receivable_in_hand_account
- cheques_under_collection_account
- returned_cheques_receivable_account
- post_dated_cheques_payable_account
- bank_charges_account
- default_bank_account

### Cheque Register

Submittable DocType:

- company
- cheque_type: Incoming / Outgoing
- cheque_number
- party_type: Customer / Supplier
- party
- amount
- currency
- bank_name
- bank_branch
- due_date
- current_status
- current_account
- linked_payment_entry
- notes
- attachment

### Cheque Movement

Submittable DocType:

- cheque
- movement_type
- from_status
- to_status
- posting_date
- amount
- journal_entry
- notes

## Incoming Cheque Lifecycle

- Draft
- Received / In Hand
- Deposited / Under Collection
- Cleared
- Returned
- Returned to Customer
- Endorsed to Supplier
- Cancelled

## Outgoing Cheque Lifecycle

- Draft
- Issued
- Cleared
- Cancelled
- Reversed

## Accounting Entries

Receive incoming cheque:

```text
Dr Cheques Receivable - In Hand
Cr Customer Receivable
```

Deposit cheque to bank:

```text
Dr Cheques Under Collection
Cr Cheques Receivable - In Hand
```

Clear cheque:

```text
Dr Bank Account
Cr Cheques Under Collection
```

Returned cheque:

```text
Dr Returned Cheques Receivable or Customer Receivable
Cr Cheques Under Collection
```

Issue outgoing cheque:

```text
Dr Supplier Payable
Cr Post Dated Cheques Payable
```

Outgoing cheque cleared:

```text
Dr Post Dated Cheques Payable
Cr Bank Account
```

## Validations

- Cheque amount must be positive.
- Cheque number is required.
- Cheque type is required.
- Party is required.
- Cannot change cheque amount after submit.
- Cannot deposit a cheque already endorsed to supplier.
- Cannot endorse a cheque already deposited to bank.
- Cannot clear a cheque unless it is deposited.
- Cannot use the same cheque number with the same bank twice.
- Movement amount must equal cheque amount.

## Reports

- Cheques In Hand
- Cheques Due This Week
- Cheques Due This Month
- Cheques Under Collection
- Returned Cheques
- Cheques by Customer/Supplier
- Cheques by Bank

## Future Server Methods

- deposit_to_bank
- mark_as_cleared
- mark_as_returned
- endorse_to_supplier
- return_to_customer
- cancel_cheque

Do not add automatic Journal Entry posting until workflows, permissions, and tests are in place.

