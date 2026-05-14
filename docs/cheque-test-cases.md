# Cheque Management Test Cases

Use these tests on `evox.localhost` after migration and build. They are written as manual ERPNext tests for Phase 1 because local chart-of-accounts, company, customer, and supplier fixtures may differ between installations.

## Register Validation

1. Create an incoming cheque with company, customer, cheque number, bank name, due date, currency, and a positive amount. Submit it and confirm the status becomes `Received / In Hand`.
2. Try to save a cheque with amount `0` or a negative amount. It should be blocked.
3. Create a second active cheque with the same company, bank name, and cheque number. It should be blocked.
4. Submit a cheque, then try to change the amount. It should be blocked.
5. Submit a cheque, then try to change the cheque number, bank name, company, currency, cheque type, due date, party type, or party. It should be blocked.
6. With strict validation enabled, create an incoming cheque for a supplier. It should be blocked.
7. With strict validation enabled, create an outgoing cheque for a customer. It should be blocked.
8. Create a draft incoming cheque with due date entered through the UI date picker. Submit it without changing fields. The submit transition from `Draft` to `Received / In Hand` should be allowed.
9. Submit a cheque, reload it, then try to change only `due_date`. It should be blocked.
10. Submit a cheque, reload it, then try to change only `amount`. It should be blocked.
11. Submit a cheque, reload it, then try to change only `cheque_number`. It should be blocked.
12. Submit an outgoing cheque from `Draft`. The submit transition from `Draft` to `Issued` should be allowed.
13. Try to type an invalid currency such as `USaw`. It should be rejected because currency is a Link to `Currency`.
14. Create a same-currency cheque. Confirm `exchange_rate` becomes `1` and `base_amount` equals `amount`.
15. Create a foreign-currency cheque. Confirm a positive `exchange_rate` is required and `base_amount = amount * exchange_rate`.
16. Submit a cheque, create any movement, then try to change `amount` or `currency`. It should be blocked.

## Incoming Lifecycle

1. From `Received / In Hand`, click `Deposit to Bank`. It should create a submitted Cheque Movement and update the cheque to `Deposited / Under Collection`.
2. From `Deposited / Under Collection`, click `Mark as Cleared`. It should update the cheque to `Cleared`.
3. Try to mark a `Received / In Hand` cheque as cleared by manually creating a movement. It should be blocked.
4. Deposit a cheque, then try to endorse it to a supplier. It should be blocked.
5. From `Received / In Hand`, click `Endorse to Supplier`. It should update the cheque to `Endorsed to Supplier`.
6. From `Received / In Hand`, click `Return to Customer`. It should update the cheque to `Returned to Customer`.
7. From `Deposited / Under Collection`, click `Mark as Returned`. It should update the cheque to `Returned` and store the return date/reason.
8. From `Returned`, click `Return to Customer`. It should update the cheque to `Returned to Customer`.

## Outgoing Lifecycle

1. Create an outgoing cheque for a supplier. Submit it and confirm the status becomes `Issued`.
2. From `Issued`, click `Mark as Cleared`. It should update the cheque to `Cleared`.
3. From `Issued`, click `Cancel Cheque`. It should update the cheque to `Cancelled`.

## Movement Validation

1. Create a movement with an amount different from the cheque amount. It should be blocked.
2. Create a movement with a different company than the cheque. It should be blocked.
3. Create a movement with a different currency than the cheque. It should be blocked.
4. Submit two movements in sequence, then try to cancel the older movement. It should be blocked.
5. Cancel the latest movement. The cheque should restore to the movement's `from_status`.
6. Select a cheque on a new Cheque Movement. Company, cheque number, party, bank, due date, amount, currency, status, and original exchange values should fetch automatically and stay read-only.
7. For `Deposit to Bank`, `Mark as Cleared`, or `Mark as Returned`, leave Bank Account empty. Submission should be blocked.
8. For `Endorse to Supplier`, leave Supplier empty. Submission should be blocked.
9. For `Mark as Returned`, `Return to Customer`, or `Cancel`, leave Reason empty. Submission should be blocked.
10. For a foreign-currency cheque, clear it with a movement exchange rate different from the original rate. Confirm movement base amount, exchange difference, and Gain/Loss/None are calculated.

## Reports

1. Open `Cheques In Hand` and confirm only `Received / In Hand` cheques are shown.
2. Open `Cheques Under Collection` and confirm only `Deposited / Under Collection` cheques are shown.
3. Open `Returned Cheques` and confirm only `Returned` cheques are shown.
4. Open `Cheques Due` and filter by due date range and status.
5. Open `Cheques by Party` and filter by customer or supplier.
