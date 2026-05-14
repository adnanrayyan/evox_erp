# Cheque Accounting Plan

This document records the planned accounting design for the cheque lifecycle. Phase 1 does not create automatic Journal Entries. The current implementation only validates and tracks cheque status movements.

Automatic Journal Entry posting is planned for Phase 2 and must be tested carefully with real EVOX/OUX accounts, permissions, cancellation behavior, and financial reports before it is enabled.

## Planned Entries

### Incoming cheque received

```text
Dr Cheques Receivable - In Hand
Cr Customer Receivable
```

### Deposit cheque to bank

```text
Dr Cheques Under Collection
Cr Cheques Receivable - In Hand
```

### Cheque cleared

```text
Dr Bank Account
Cr Cheques Under Collection
```

### Cheque returned

```text
Dr Returned Cheques Receivable
Cr Cheques Under Collection
```

### Return cheque to customer / reopen receivable

```text
Dr Customer Receivable
Cr Returned Cheques Receivable
```

### Outgoing cheque issued

```text
Dr Supplier Payable
Cr Post Dated Cheques Payable
```

### Outgoing cheque cleared

```text
Dr Post Dated Cheques Payable
Cr Bank Account
```

## Phase 2 Notes

- Journal Entry creation should start as draft-only until reviewed.
- Cheque Settings stores the account defaults, but the fields are intentionally not mandatory yet.
- Cheque Register stores original cheque currency, company currency, exchange rate, and base amount at cheque creation time.
- Cheque Movement stores movement exchange rate, movement base amount, and exchange difference for future accounting-impact movements.
- Phase 1 calculates exchange difference for clear/collection movements only; it does not post exchange gain or loss Journal Entries.
- Cancellation and reversal behavior must be tested against submitted Journal Entries before any automatic posting is enabled.
- Bank charges should be handled explicitly and should not be inferred from a cheque movement amount.
- The movement amount must always equal the cheque amount; partial clearing or partial endorsement is out of scope for Phase 1.
