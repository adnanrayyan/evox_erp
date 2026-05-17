import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from evox_erp.cheque_management.cheque_lifecycle import (
    calculates_exchange_difference,
    get_to_status,
    is_bank_movement,
    normalize_movement_type,
    requires_reason,
    requires_supplier,
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
        self.validate_exchange_rate()

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
        self.company = cheque.company
        self.cheque_number = cheque.cheque_number
        self.amount = cheque.amount
        self.currency = cheque.currency
        self.company_currency = cheque.company_currency or get_company_currency(cheque.company)
        self.bank_name = cheque.bank_name
        self.bank_branch = cheque.bank_branch
        self.due_date = cheque.due_date
        self.current_status = cheque.current_status
        self.party_type = cheque.party_type
        self.party = cheque.party
        self.from_status = cheque.current_status

        if not self.posting_date:
            self.posting_date = today()

        if self.movement_type:
            self.to_status = get_to_status(cheque.cheque_type, cheque.current_status, self.movement_type)

        self.set_exchange_values_from_cheque(cheque)

        if is_bank_movement(self.movement_type) and not self.bank_account:
            self.bank_account = cheque.deposit_bank_account or frappe.db.get_single_value(
                "Cheque Settings", "default_bank_account"
            )

    def set_exchange_values_from_cheque(self, cheque):
        original_exchange_rate = flt(cheque.exchange_rate) or 1
        if cheque.currency == self.company_currency:
            original_exchange_rate = 1

        self.original_exchange_rate = original_exchange_rate
        self.original_base_amount = (
            flt(cheque.base_amount) or flt(cheque.amount) * original_exchange_rate
        )

        if cheque.currency == self.company_currency or not calculates_exchange_difference(self.movement_type):
            self.movement_exchange_rate = original_exchange_rate
        elif flt(self.movement_exchange_rate) <= 0:
            self.movement_exchange_rate = original_exchange_rate

        movement_exchange_rate = flt(self.movement_exchange_rate) or 1
        self.movement_base_amount = flt(cheque.amount) * movement_exchange_rate

        if cheque.currency == self.company_currency or not calculates_exchange_difference(self.movement_type):
            self.exchange_difference = 0
        else:
            self.exchange_difference = flt(self.movement_base_amount) - flt(self.original_base_amount)

        self.exchange_difference_type = get_exchange_difference_type(self.exchange_difference)

    def validate_cheque_is_submitted(self, cheque):
        if cheque.docstatus != 1:
            frappe.throw(_("Cheque {0} must be submitted before a movement can be created.").format(cheque.name))

    def validate_amount_company_currency(self, cheque):
        if self.company != cheque.company:
            frappe.throw(_("Movement company must match the cheque company."))

        if self.currency != cheque.currency:
            frappe.throw(_("Movement currency must match the cheque currency."))

        cheque_company_currency = cheque.company_currency or get_company_currency(cheque.company)
        if self.company_currency != cheque_company_currency:
            frappe.throw(_("Movement company currency must match the cheque company currency."))

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
        expected_to_status = get_to_status(cheque.cheque_type, cheque.current_status, self.movement_type)
        if self.from_status != cheque.current_status:
            frappe.throw(_("Movement from status must match the cheque current status."))

        if self.to_status != expected_to_status:
            frappe.throw(_("Movement to status is invalid for the selected movement type."))

    def validate_required_transition_fields(self):
        movement_type = normalize_movement_type(self.movement_type)

        if requires_supplier(movement_type) and not self.supplier:
            frappe.throw(_("Supplier is required when endorsing a cheque."))

        if is_bank_movement(movement_type) and not self.bank_account:
            frappe.throw(_("Bank Account is required for this cheque movement."))

        if requires_reason(movement_type) and not self.reason:
            frappe.throw(_("Reason is required for this cheque movement."))

    def validate_account_company(self):
        if not (self.company and self.bank_account):
            return

        account_company = frappe.db.get_value("Account", self.bank_account, "company")
        if account_company and account_company != self.company:
            frappe.throw(_("Bank account must belong to movement company {0}.").format(self.company))

    def validate_exchange_rate(self):
        if self.currency == self.company_currency:
            if flt(self.movement_exchange_rate) != 1:
                frappe.throw(_("Movement Exchange Rate must be 1 when cheque currency matches company currency."))
            if flt(self.exchange_difference) != 0:
                frappe.throw(_("Exchange Difference must be zero when cheque currency matches company currency."))
            return

        if calculates_exchange_difference(self.movement_type) and flt(self.movement_exchange_rate) <= 0:
            frappe.throw(_("Movement Exchange Rate is required for this movement."))

    def update_cheque_register(self):
        cheque = self.get_cheque()
        movement_type = normalize_movement_type(self.movement_type)
        cheque.flags.allow_status_update = True
        cheque.current_status = self.to_status

        if movement_type == "Deposit to Bank":
            cheque.deposit_bank_account = self.bank_account
            cheque.deposit_date = self.posting_date
        elif movement_type == "Mark as Cleared":
            cheque.clearance_date = self.posting_date
        elif movement_type == "Mark as Returned":
            cheque.return_date = self.posting_date
            cheque.return_reason = self.reason
        elif movement_type == "Endorse to Supplier":
            cheque.endorsed_to_supplier = self.supplier
            cheque.endorsed_date = self.posting_date
        # "Return to Customer" is a physical/admin handback; only status is updated above.

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
        movement_type = normalize_movement_type(self.movement_type)

        if movement_type == "Deposit to Bank":
            if cheque.deposit_bank_account == self.bank_account:
                cheque.deposit_bank_account = None
            if str(cheque.deposit_date or "") == str(self.posting_date or ""):
                cheque.deposit_date = None
        elif movement_type == "Mark as Cleared":
            if str(cheque.clearance_date or "") == str(self.posting_date or ""):
                cheque.clearance_date = None
        elif movement_type == "Mark as Returned":
            if str(cheque.return_date or "") == str(self.posting_date or ""):
                cheque.return_date = None
            if cheque.return_reason == self.reason:
                cheque.return_reason = None
        elif movement_type == "Endorse to Supplier":
            if cheque.endorsed_to_supplier == self.supplier:
                cheque.endorsed_to_supplier = None
            if str(cheque.endorsed_date or "") == str(self.posting_date or ""):
                cheque.endorsed_date = None


def get_company_currency(company):
    if not company:
        return None
    return frappe.db.get_value("Company", company, "default_currency")


def get_exchange_difference_type(exchange_difference):
    difference = flt(exchange_difference)
    if difference > 0:
        return "Gain"
    if difference < 0:
        return "Loss"
    return "None"


@frappe.whitelist()
def get_cheque_details(cheque):
    cheque_doc = frappe.get_doc("Cheque Register", cheque)
    cheque_doc.check_permission("read")

    company_currency = cheque_doc.company_currency or get_company_currency(cheque_doc.company)
    exchange_rate = flt(cheque_doc.exchange_rate) or 1
    if cheque_doc.currency == company_currency:
        exchange_rate = 1
    base_amount = flt(cheque_doc.base_amount) or flt(cheque_doc.amount) * exchange_rate

    return {
        "company": cheque_doc.company,
        "cheque_number": cheque_doc.cheque_number,
        "amount": cheque_doc.amount,
        "currency": cheque_doc.currency,
        "company_currency": company_currency,
        "exchange_rate": exchange_rate,
        "base_amount": base_amount,
        "due_date": cheque_doc.due_date,
        "current_status": cheque_doc.current_status,
        "party_type": cheque_doc.party_type,
        "party": cheque_doc.party,
        "bank_name": cheque_doc.bank_name,
        "bank_branch": cheque_doc.bank_branch,
        "deposit_bank_account": cheque_doc.deposit_bank_account,
    }
