import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt, getdate, today

from evox_erp.cheque_management.cheque_lifecycle import (
    DRAFT_STATUS,
    INACTIVE_STATUSES,
    get_initial_status,
)


IMMUTABLE_AFTER_SUBMIT = (
    "company",
    "cheque_type",
    "cheque_number",
    "bank_name",
    "due_date",
    "currency",
    "amount",
    "company_currency",
    "exchange_rate",
    "base_amount",
    "party_type",
    "party",
)

DATE_FIELDS = {"due_date"}
FLOAT_FIELDS = {"amount", "exchange_rate", "base_amount"}
EXCHANGE_FIELDS = {"company_currency", "exchange_rate", "base_amount"}


class ChequeRegister(Document):
    def validate(self):
        self.set_default_status()
        self.set_company_currency()
        self.validate_required_values()
        self.validate_currency_links()
        self.validate_positive_amount()
        self.validate_exchange_rate()
        self.calculate_base_amount()
        self.validate_expected_party_type()
        self.validate_duplicate_active_cheque()
        self.validate_amount_currency_not_used_in_movement()
        self.validate_after_submit_changes()

    def before_submit(self):
        self.current_status = get_initial_status(self.cheque_type)

    def on_submit(self):
        self.add_comment(
            "Comment",
            _("Cheque submitted with status {0}.").format(frappe.bold(self.current_status)),
        )

    def before_cancel(self):
        # allow_direct_cancel is set programmatically by Customer Receipt and Company
        # Cheque Issue cancel flows — do not set this flag from user-facing code.
        if self.flags.get("allow_direct_cancel"):
            return
        frappe.throw(_("Use the Cancel Cheque action so the lifecycle change is recorded as a Cheque Movement."))

    def set_default_status(self):
        if self.docstatus == 0:
            self.current_status = DRAFT_STATUS

    def validate_required_values(self):
        required_fields = (
            "company",
            "cheque_type",
            "cheque_number",
            "bank_name",
            "due_date",
            "currency",
            "amount",
            "company_currency",
            "party_type",
            "party",
        )
        for fieldname in required_fields:
            if not self.get(fieldname):
                frappe.throw(
                    _("{0} is required.").format(frappe.bold(self.meta.get_label(fieldname)))
                )

    def validate_positive_amount(self):
        if flt(self.amount) <= 0:
            frappe.throw(_("Cheque amount must be greater than zero."))

    def set_company_currency(self):
        if self.company and (self.docstatus == 0 or not self.company_currency):
            self.company_currency = frappe.db.get_value(
                "Company", self.company, "default_currency"
            )

        if not self.currency:
            self.currency = frappe.db.get_single_value("Cheque Settings", "default_currency")

    def validate_currency_links(self):
        for fieldname in ("currency", "company_currency"):
            currency = self.get(fieldname)
            if currency and not frappe.db.exists("Currency", currency):
                frappe.throw(
                    _("{0} must be an existing Currency.").format(
                        frappe.bold(self.meta.get_label(fieldname))
                    )
                )

    def validate_exchange_rate(self):
        if not (self.currency and self.company_currency):
            return

        if self.currency == self.company_currency:
            self.exchange_rate = 1
            return

        if flt(self.exchange_rate) <= 0:
            frappe.throw(
                _("Exchange Rate is required when cheque currency differs from company currency.")
            )

    def calculate_base_amount(self):
        if not self.amount:
            return

        exchange_rate = flt(self.exchange_rate) or 1
        self.base_amount = flt(self.amount) * exchange_rate

    def validate_expected_party_type(self):
        expected_party_type = None
        if self.cheque_type == "Incoming":
            expected_party_type = "Customer"
        elif self.cheque_type == "Outgoing":
            expected_party_type = "Supplier"

        if not expected_party_type or self.party_type == expected_party_type:
            return

        message = _("{0} cheques should normally use party type {1}.").format(
            frappe.bold(self.cheque_type), frappe.bold(expected_party_type)
        )
        if is_strict_validation_enabled():
            frappe.throw(message)

        frappe.msgprint(message, indicator="orange", alert=True)

    def validate_duplicate_active_cheque(self):
        if not (self.company and self.bank_name and self.cheque_number):
            return

        if self.current_status in INACTIVE_STATUSES:
            return

        filters = {
            "company": self.company,
            "bank_name": self.bank_name,
            "cheque_number": self.cheque_number,
            "docstatus": ["<", 2],
            "current_status": ["not in", list(INACTIVE_STATUSES)],
        }
        if not self.is_new():
            filters["name"] = ["!=", self.name]

        duplicate = frappe.db.get_value("Cheque Register", filters, "name")
        if duplicate:
            frappe.throw(
                _("Active cheque {0} already exists for company {1}, bank {2}, and cheque number {3}.").format(
                    frappe.bold(duplicate),
                    frappe.bold(self.company),
                    frappe.bold(self.bank_name),
                    frappe.bold(self.cheque_number),
                )
            )

    def validate_amount_currency_not_used_in_movement(self):
        previous = self.get_doc_before_save()
        if not previous or not self.name:
            return

        if not frappe.db.exists(
            "Cheque Movement", {"cheque": self.name, "docstatus": ["<", 2]}
        ):
            return

        for fieldname in ("amount", "currency", "company_currency", "exchange_rate", "base_amount"):
            if (
                fieldname in EXCHANGE_FIELDS
                and not previous.get(fieldname)
                and self.get(fieldname)
            ):
                continue

            if has_immutable_field_changed(previous, self, fieldname):
                frappe.throw(
                    _("{0} cannot be changed after the cheque has movements.").format(
                        frappe.bold(self.meta.get_label(fieldname))
                    )
                )

    def validate_after_submit_changes(self):
        previous = self.get_doc_before_save()
        if not previous:
            return

        if previous.docstatus != 1 or self.docstatus != 1:
            return

        for fieldname in IMMUTABLE_AFTER_SUBMIT:
            if (
                fieldname in EXCHANGE_FIELDS
                and not previous.get(fieldname)
                and self.get(fieldname)
            ):
                continue

            if has_immutable_field_changed(previous, self, fieldname):
                frappe.throw(
                    _("{0} cannot be changed after the cheque is submitted.").format(
                        frappe.bold(self.meta.get_label(fieldname))
                    )
                )

        if previous.current_status != self.current_status and not self.flags.allow_status_update:
            frappe.throw(
                _("Cheque status is controlled by Cheque Movement records and cannot be edited manually.")
            )


def has_immutable_field_changed(previous, current, fieldname):
    previous_value = previous.get(fieldname)
    current_value = current.get(fieldname)

    if fieldname in DATE_FIELDS:
        if not previous_value and not current_value:
            return False
        return getdate(previous_value) != getdate(current_value)

    if fieldname in FLOAT_FIELDS:
        return flt(previous_value) != flt(current_value)

    return cstr(previous_value).strip() != cstr(current_value).strip()


def is_strict_validation_enabled():
    try:
        value = frappe.db.get_single_value("Cheque Settings", "enable_strict_validation")
    except Exception:
        return True

    if value is None:
        return True
    return cint(value)


def _get_cheque_for_action(cheque_name):
    cheque = frappe.get_doc("Cheque Register", cheque_name)
    if cheque.docstatus != 1:
        frappe.throw(_("Cheque {0} must be submitted before lifecycle actions can be used.").format(cheque.name))
    cheque.check_permission("write")
    return cheque


def _create_movement(
    cheque_name,
    movement_type,
    posting_date=None,
    bank_account=None,
    supplier=None,
    reason=None,
    movement_exchange_rate=None,
    notes=None,
):
    cheque = _get_cheque_for_action(cheque_name)
    movement = frappe.new_doc("Cheque Movement")
    movement.update(
        {
            "company": cheque.company,
            "cheque": cheque.name,
            "movement_type": movement_type,
            "posting_date": posting_date or today(),
            "amount": cheque.amount,
            "currency": cheque.currency,
            "company_currency": cheque.company_currency,
            "original_exchange_rate": cheque.exchange_rate,
            "original_base_amount": cheque.base_amount,
            "movement_exchange_rate": movement_exchange_rate or cheque.exchange_rate,
            "party_type": cheque.party_type,
            "party": cheque.party,
            "bank_account": bank_account,
            "supplier": supplier,
            "reason": reason,
            "notes": notes,
        }
    )
    movement.insert()
    movement.submit()

    return {"status": movement.to_status, "movement": movement.name, "journal_entry": movement.journal_entry}


@frappe.whitelist()
def deposit_to_bank(cheque_name, bank_account=None, posting_date=None, notes=None):
    return _create_movement(
        cheque_name,
        "Deposit to Bank",
        bank_account=bank_account,
        posting_date=posting_date,
        notes=notes,
    )


@frappe.whitelist()
def mark_as_cleared(cheque_name, bank_account=None, posting_date=None, movement_exchange_rate=None, notes=None):
    return _create_movement(
        cheque_name,
        "Mark as Cleared",
        bank_account=bank_account,
        posting_date=posting_date,
        movement_exchange_rate=movement_exchange_rate,
        notes=notes,
    )


@frappe.whitelist()
def mark_as_returned(cheque_name, bank_account=None, posting_date=None, reason=None, notes=None):
    return _create_movement(
        cheque_name,
        "Mark as Returned",
        bank_account=bank_account,
        posting_date=posting_date,
        reason=reason,
        notes=notes,
    )


@frappe.whitelist()
def return_to_customer(cheque_name, posting_date=None, reason=None, notes=None):
    return _create_movement(
        cheque_name,
        "Return to Customer",
        posting_date=posting_date,
        reason=reason,
        notes=notes,
    )


@frappe.whitelist()
def endorse_to_supplier(cheque_name, supplier, posting_date=None, notes=None):
    return _create_movement(
        cheque_name,
        "Endorse to Supplier",
        posting_date=posting_date,
        supplier=supplier,
        notes=notes,
    )


@frappe.whitelist()
def cancel_cheque(cheque_name, posting_date=None, reason=None):
    return _create_movement(
        cheque_name,
        "Cancel",
        posting_date=posting_date,
        reason=reason,
    )
