import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from evox_erp.cheque_management.cheque_lifecycle import (
    INACTIVE_STATUSES,
    get_to_status,
)


class ChequeMovement(Document):
    def before_validate(self):
        self.set_defaults_from_cheque()

    def validate(self):
        cheque = self.get_cheque()
        self.validate_cheque_is_submitted(cheque)
        self.validate_amount_company_currency(cheque)
        self.validate_party_fields(cheque)
        self.validate_transition(cheque)
        self.validate_required_transition_fields()
        self.validate_account_company()

    def on_submit(self):
        self.update_cheque_register()
        self.create_accounting_entry_for_movement()

    def before_cancel(self):
        self.validate_latest_movement_for_cancel()

    def on_cancel(self):
        self.restore_cheque_status_after_cancel()

    def get_cheque(self):
        if not self.cheque:
            frappe.throw(_("Cheque is required."))
        return frappe.get_doc("Cheque Register", self.cheque)

    def set_defaults_from_cheque(self):
        if not self.cheque:
            return

        cheque = frappe.get_doc("Cheque Register", self.cheque)
        self.company = self.company or cheque.company
        self.amount = self.amount if self.amount not in (None, "") else cheque.amount
        self.currency = self.currency or cheque.currency
        self.party_type = cheque.party_type
        self.party = cheque.party
        self.from_status = cheque.current_status
        if not self.posting_date:
            self.posting_date = today()

        if self.movement_type:
            self.to_status = get_to_status(cheque.cheque_type, cheque.current_status, self.movement_type)

        if self.movement_type == "Deposit to Bank" and not self.bank_account:
            self.bank_account = frappe.db.get_single_value("Cheque Settings", "default_bank_account")

    def validate_cheque_is_submitted(self, cheque):
        if cheque.docstatus != 1:
            frappe.throw(_("Cheque {0} must be submitted before a movement can be created.").format(cheque.name))

    def validate_amount_company_currency(self, cheque):
        if self.company != cheque.company:
            frappe.throw(_("Movement company must match the cheque company."))

        if self.currency != cheque.currency:
            frappe.throw(_("Movement currency must match the cheque currency."))

        if flt(self.amount) != flt(cheque.amount):
            frappe.throw(
                _("Movement amount {0} must equal cheque amount {1}.").format(
                    frappe.bold(self.amount), frappe.bold(cheque.amount)
                )
            )

    def validate_party_fields(self, cheque):
        if self.party_type != cheque.party_type or self.party != cheque.party:
            frappe.throw(_("Movement party must match the cheque party."))

    def validate_transition(self, cheque):
        if cheque.current_status in INACTIVE_STATUSES and self.movement_type != "Reverse":
            frappe.throw(_("Cannot create a movement for a cheque in status {0}.").format(cheque.current_status))

        expected_to_status = get_to_status(cheque.cheque_type, cheque.current_status, self.movement_type)
        if self.from_status != cheque.current_status:
            frappe.throw(_("Movement from status must match the cheque current status."))

        if self.to_status != expected_to_status:
            frappe.throw(_("Movement to status is invalid for the selected movement type."))

    def validate_required_transition_fields(self):
        if self.movement_type == "Endorse to Supplier" and not self.supplier:
            frappe.throw(_("Supplier is required when endorsing a cheque."))

    def validate_account_company(self):
        if not (self.company and self.bank_account):
            return

        account_company = frappe.db.get_value("Account", self.bank_account, "company")
        if account_company and account_company != self.company:
            frappe.throw(_("Bank account must belong to movement company {0}.").format(self.company))

    def update_cheque_register(self):
        cheque = self.get_cheque()
        cheque.flags.allow_status_update = True
        cheque.current_status = self.to_status

        if self.movement_type == "Deposit to Bank":
            cheque.deposit_bank_account = self.bank_account
            cheque.deposit_date = self.posting_date
        elif self.movement_type == "Mark as Cleared":
            cheque.clearance_date = self.posting_date
        elif self.movement_type == "Mark as Returned":
            cheque.return_date = self.posting_date
            cheque.return_reason = self.reason
        elif self.movement_type == "Return to Customer":
            cheque.return_date = self.posting_date
            cheque.return_reason = self.reason
        elif self.movement_type == "Endorse to Supplier":
            cheque.endorsed_to_supplier = self.supplier
            cheque.endorsed_date = self.posting_date

        cheque.save(ignore_permissions=True)
        cheque.add_comment(
            "Comment",
            _("Cheque movement {0}: {1} -> {2}.").format(
                frappe.bold(self.movement_type),
                frappe.bold(self.from_status),
                frappe.bold(self.to_status),
            ),
        )

    def create_accounting_entry_for_movement(self):
        # TODO: Phase 2 will create carefully tested draft Journal Entries here.
        # Phase 1 intentionally records lifecycle status only and does not post GL.
        return None

    def validate_latest_movement_for_cancel(self):
        latest = frappe.get_all(
            "Cheque Movement",
            filters={"cheque": self.cheque, "docstatus": 1},
            fields=["name"],
            order_by="creation desc, name desc",
            limit=1,
        )
        latest_name = latest[0].name if latest else None
        if latest_name != self.name:
            frappe.throw(_("Only the latest submitted Cheque Movement can be cancelled."))

        cheque = self.get_cheque()
        if cheque.current_status != self.to_status:
            frappe.throw(_("Cheque status has changed and this movement cannot be cancelled safely."))

    def restore_cheque_status_after_cancel(self):
        cheque = self.get_cheque()
        cheque.flags.allow_status_update = True
        cheque.current_status = self.from_status
        self.clear_tracking_fields_for_cancel(cheque)
        cheque.save(ignore_permissions=True)
        cheque.add_comment(
            "Comment",
            _("Cancelled cheque movement {0}; status restored to {1}.").format(
                frappe.bold(self.name), frappe.bold(self.from_status)
            ),
        )

    def clear_tracking_fields_for_cancel(self, cheque):
        if self.movement_type == "Deposit to Bank":
            if cheque.deposit_bank_account == self.bank_account:
                cheque.deposit_bank_account = None
            if str(cheque.deposit_date or "") == str(self.posting_date or ""):
                cheque.deposit_date = None
        elif self.movement_type == "Mark as Cleared":
            if str(cheque.clearance_date or "") == str(self.posting_date or ""):
                cheque.clearance_date = None
        elif self.movement_type in ("Mark as Returned", "Return to Customer"):
            if str(cheque.return_date or "") == str(self.posting_date or ""):
                cheque.return_date = None
            if cheque.return_reason == self.reason:
                cheque.return_reason = None
        elif self.movement_type == "Endorse to Supplier":
            if cheque.endorsed_to_supplier == self.supplier:
                cheque.endorsed_to_supplier = None
            if str(cheque.endorsed_date or "") == str(self.posting_date or ""):
                cheque.endorsed_date = None

