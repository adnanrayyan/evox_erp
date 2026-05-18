import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from evox_erp.cheque_management.cheque_accounting import (
    cancel_journal_entry,
    get_party_account_for_cheque,
    get_post_dated_cheques_payable_account,
    make_journal_entry,
    validate_cheque_settings,
)

_CHEQUE_REGISTER = "Cheque Register"
_STATUS_ISSUED = "Issued"
_STATUS_CLEARED = "Cleared"
_STATUS_CANCELLED = "Cancelled"


class CompanyChequeIssue(Document):
    def validate(self):
        self.set_party_account()
        self.set_defaults()
        self.validate_required_fields()
        self.validate_positive_amount()
        self.validate_exchange_rate()
        self.calculate_base_amount()
        self.validate_duplicate_cheque_number()

    def before_submit(self):
        self.validate_cheque_settings_accounts()

    def on_submit(self):
        cheque_register = self.create_cheque_register()
        je = self.create_issuance_journal_entry(cheque_register)
        self.db_set("cheque_register", cheque_register.name, update_modified=False)
        self.db_set("journal_entry", je.name, update_modified=False)
        self.db_set("status", "Issued", update_modified=False)
        frappe.db.set_value(_CHEQUE_REGISTER, cheque_register.name, {
            "company_cheque_issue": self.name,
            "linked_journal_entry": je.name,
        })

    def before_cancel(self):
        self.validate_can_cancel()

    def on_cancel(self):
        self.perform_cancel()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def set_party_account(self):
        if self.company and self.party_type and self.party:
            try:
                self.party_account = get_party_account_for_cheque(
                    self.party_type, self.party, self.company
                )
            except Exception:
                pass

    def set_defaults(self):
        if not self.posting_date:
            self.posting_date = today()
        if not self.currency and self.company:
            company_currency = frappe.db.get_value("Company", self.company, "default_currency")
            if company_currency:
                self.currency = company_currency

    def validate_required_fields(self):
        required = {
            "company": "Company",
            "posting_date": "Posting Date",
            "party_type": "Party Type",
            "party": "Party",
            "cheque_number": "Cheque Number",
            "bank_account": "Bank Account",
            "due_date": "Due / Cheque Date",
            "currency": "Currency",
            "amount": "Amount",
        }
        for field, label in required.items():
            if not self.get(field):
                frappe.throw(_("{0} is required.").format(frappe.bold(label)))

    def validate_positive_amount(self):
        if flt(self.amount) <= 0:
            frappe.throw(_("Amount must be greater than zero."))

    def validate_exchange_rate(self):
        if not self.company or not self.currency:
            return
        company_currency = frappe.db.get_value("Company", self.company, "default_currency")
        if self.currency == company_currency:
            self.exchange_rate = 1
        elif flt(self.exchange_rate) <= 0:
            frappe.throw(_("Exchange Rate is required when currency differs from company currency."))

    def calculate_base_amount(self):
        exchange_rate = flt(self.exchange_rate) or 1
        self.base_amount = flt(self.amount) * exchange_rate

    def validate_duplicate_cheque_number(self):
        if not (self.company and self.cheque_number):
            return
        filters = {
            "company": self.company,
            "cheque_number": self.cheque_number,
            "docstatus": ["<", 2],
        }
        if not self.is_new():
            filters["name"] = ["!=", self.name]
        existing = frappe.db.get_value("Company Cheque Issue", filters, "name")
        if existing:
            frappe.throw(
                _("An outgoing cheque with number {0} already exists for company {1}: {2}").format(
                    frappe.bold(self.cheque_number),
                    frappe.bold(self.company),
                    frappe.bold(existing),
                )
            )
        # Also check Cheque Register for the same number to avoid conflicts with incoming
        existing_cr = frappe.db.get_value(
            _CHEQUE_REGISTER,
            {
                "company": self.company,
                "cheque_number": self.cheque_number,
                "cheque_type": "Outgoing",
                "docstatus": ["<", 2],
            },
            "name",
        )
        if existing_cr:
            frappe.throw(
                _("An outgoing Cheque Register with number {0} already exists: {1}").format(
                    frappe.bold(self.cheque_number), frappe.bold(existing_cr)
                )
            )

    def validate_cheque_settings_accounts(self):
        validate_cheque_settings(self.company, ["post_dated_cheques_payable_account"])
        if not self.party_account:
            self.party_account = get_party_account_for_cheque(
                self.party_type, self.party, self.company
            )
        if not self.bank_account:
            frappe.throw(_("Bank Account is required."))

    # ------------------------------------------------------------------
    # Submit: create Cheque Register + issuance JE
    # ------------------------------------------------------------------

    def create_cheque_register(self):
        cheque = frappe.new_doc(_CHEQUE_REGISTER)
        cheque.update({
            "company": self.company,
            "cheque_type": "Outgoing",
            "cheque_number": self.cheque_number,
            "bank_name": frappe.db.get_value("Account", self.bank_account, "account_name") or self.bank_account,
            "due_date": self.due_date,
            "currency": self.currency,
            "amount": flt(self.amount),
            "exchange_rate": flt(self.exchange_rate) or 1,
            "party_type": self.party_type,
            "party": self.party,
            "company_cheque_issue": self.name,
        })
        cheque.insert(ignore_permissions=True)
        cheque.submit()
        return cheque

    def create_issuance_journal_entry(self, cheque_register):
        post_dated_payable = get_post_dated_cheques_payable_account(self.company)
        party_account = self.party_account or get_party_account_for_cheque(
            self.party_type, self.party, self.company
        )
        amount = flt(cheque_register.base_amount) or flt(cheque_register.amount)

        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {
                    "account": party_account,
                    "debit_in_account_currency": amount,
                    "party_type": self.party_type,
                    "party": self.party,
                },
                {"account": post_dated_payable, "credit_in_account_currency": amount},
            ],
            remarks=_("Outgoing Company Cheque {0} issued to {1} {2}").format(
                self.name, self.party_type, self.party
            ),
            ref_doctype="Company Cheque Issue",
            ref_name=self.name,
        )

    # ------------------------------------------------------------------
    # Cancel: only allowed if cheque is still Issued with no movements
    # ------------------------------------------------------------------

    def validate_can_cancel(self):
        if not self.cheque_register:
            return

        cheque_status = frappe.db.get_value(_CHEQUE_REGISTER, self.cheque_register, "current_status")
        if cheque_status == _STATUS_CLEARED:
            frappe.throw(
                _("Cannot cancel this Company Cheque Issue. "
                  "Cheque {0} has already been cleared. "
                  "Once cleared, the cheque cannot be cancelled.").format(
                    frappe.bold(self.cheque_register)
                )
            )

        movement_count = frappe.db.count(
            "Cheque Movement",
            {"cheque": self.cheque_register, "docstatus": 1},
        )
        if movement_count > 0:
            frappe.throw(
                _("Cannot cancel this Company Cheque Issue. "
                  "Cheque {0} has {1} submitted movement(s). "
                  "Please cancel the latest cheque movement first.").format(
                    frappe.bold(self.cheque_register), movement_count
                )
            )

    def perform_cancel(self):
        # Step 1: Cancel the issuance Journal Entry only (no additional reversal JE)
        cancel_journal_entry(self.journal_entry, ignore_missing=True)

        # Step 2: Cancel the Cheque Register directly via flag bypass
        if self.cheque_register:
            cheque = frappe.get_doc(_CHEQUE_REGISTER, self.cheque_register)
            if cheque.docstatus == 1:
                cheque.flags.allow_direct_cancel = True
                cheque.cancel()

        self.db_set("status", _STATUS_CANCELLED, update_modified=False)
