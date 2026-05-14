import frappe
from frappe import _
from frappe.model.document import Document


ACCOUNT_FIELDS = (
    "cheques_receivable_in_hand_account",
    "cheques_under_collection_account",
    "returned_cheques_receivable_account",
    "post_dated_cheques_payable_account",
    "bank_charges_account",
    "default_bank_account",
)


class ChequeSettings(Document):
    def validate(self):
        self.validate_account_companies()

    def validate_account_companies(self):
        if not self.company:
            return

        for fieldname in ACCOUNT_FIELDS:
            account = self.get(fieldname)
            if not account:
                continue

            account_company = frappe.db.get_value("Account", account, "company")
            if account_company and account_company != self.company:
                label = self.meta.get_label(fieldname)
                frappe.throw(
                    _("{0} must belong to company {1}.").format(
                        frappe.bold(label), frappe.bold(self.company)
                    )
                )

    # TODO: Phase 2 accounting integration will read these account defaults
    # when creating draft Journal Entry records for cheque lifecycle movements.

