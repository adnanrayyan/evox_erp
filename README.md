# EVOX ERP Custom Frappe App

هذا المستودع مخصص لكل التخصيصات التجارية لمجموعة EVOX/OUX داخل ERPNext.

القاعدة الأساسية: لا نعدّل ERPNext core ولا Frappe core. أي ميزة جديدة، DocType، workflow، report، validation، أو custom field يجب أن يكون داخل app `evox_erp`.

## Current Status

This repository now contains a minimal valid Frappe app package named `evox_erp`.

It is intentionally small: it provides app metadata, hooks, module registration, and documentation. Business DocTypes such as Cheque Register should be created through Frappe/Bench migrations in the next implementation phase.

## Install on ERPNext Site

```bash
bench get-app https://github.com/adnanrayyan/evox_erp.git
bench --site SITE_NAME install-app evox_erp
bench --site SITE_NAME migrate
bench build --app evox_erp
bench --site SITE_NAME clear-cache
```

في local production يمكنك استخدام سكربت infra:

```powershell
cd ..\evox-erp-infra
.\scripts\windows\install-custom-app.ps1
```

## Develop Locally

استخدم Frappe Docker devcontainer من مستودع `frappe_docker`:

```powershell
cd ..\frappe_docker
Copy-Item -Recurse devcontainer-example .devcontainer
```

ثم من VS Code:

```text
Dev Containers: Reopen in Container
```

داخل الـ container:

```bash
python installer.py
bench new-site evox-dev.localhost
bench new-app evox_erp
bench --site evox-dev.localhost install-app evox_erp
bench start
```

## Planned Cheque Module

الهدف الأول لهذا app هو Cheque Management قوي يناسب العمل المحلي.

Planned DocTypes:

- Cheque Settings
- Cheque Register
- Cheque Movement

Planned controllers:

- `cheque_settings.py`
- `cheque_register.py`
- `cheque_movement.py`

Planned client scripts:

- `cheque_register.js`

Planned reports:

- Cheques In Hand
- Cheques Due
- Cheques Under Collection
- Returned Cheques

Planned fixtures:

- Custom fields
- Workflows
- Roles
- Print formats, if needed

## First Skeleton to Generate Later

When Bench is available, create these DocTypes through Frappe/Bench instead of hand-writing random metadata:

### Cheque Settings

Singleton DocType with fields:

- company
- cheques_receivable_in_hand_account
- cheques_under_collection_account
- returned_cheques_receivable_account
- post_dated_cheques_payable_account
- bank_charges_account
- default_bank_account

### Cheque Register

Submittable DocType with fields:

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

Submittable DocType with fields:

- cheque
- movement_type
- from_status
- to_status
- posting_date
- amount
- journal_entry
- notes

## Initial Validations

- Cheque amount must be positive.
- Cheque number is required.
- Cheque type is required.
- Party is required.
- Do not allow amount change after submit.
- Movement amount must equal cheque amount.

## Future Server Methods

Add these methods after the DocTypes and tests exist:

- `deposit_to_bank`
- `mark_as_cleared`
- `mark_as_returned`
- `endorse_to_supplier`
- `return_to_customer`
- `cancel_cheque`

Do not implement automatic Journal Entry posting until the workflow and validations are tested.
