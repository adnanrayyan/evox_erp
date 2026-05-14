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
    "party_type",
    "party",
)

DATE_FIELDS = {"due_date"}
FLOAT_FIELDS = {"amount"}


class ChequeRegister(Document):
    def validate(self):
        self.set_default_status()
        self.validate_required_values()
        self.validate_positive_amount()
        self.validate_expected_party_type()
        self.validate_duplicate_active_cheque()
        self.validate_after_submit_changes()

    def before_submit(self):
        self.current_status = get_initial_status(self.cheque_type)

    def on_submit(self):
        self.add_comment(
            "Comment",
            _("Cheque submitted with status {0}.").format(frappe.bold(self.current_status)),
        )

    def before_cancel(self):
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

    def validate_after_submit_changes(self):
        previous = self.get_doc_before_save()
        if not previous:
            return

        if previous.docstatus != 1 or self.docstatus != 1:
            return

        for fieldname in IMMUTABLE_AFTER_SUBMIT:
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

    # TODO: Phase 2 will optionally create a draft Journal Entry for this movement.
    return {"status": movement.to_status, "movement": movement.name}


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
def mark_as_cleared(cheque_name, posting_date=None, notes=None):
    return _create_movement(
        cheque_name,
        "Mark as Cleared",
        posting_date=posting_date,
        notes=notes,
    )


@frappe.whitelist()
def mark_as_returned(cheque_name, posting_date=None, reason=None, notes=None):
    return _create_movement(
        cheque_name,
        "Mark as Returned",
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
