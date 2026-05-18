import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from evox_erp.cheque_management.cheque_accounting import (
    cancel_journal_entry,
    cancel_payment_entry,
    get_cheques_in_hand_account,
    get_customer_receivable_account,
    make_journal_entry,
    make_payment_entry,
    validate_cheque_settings,
)

_CHEQUE_REGISTER = "Cheque Register"
_MODE_CASH = "Cash"
_MODE_CHEQUE = "Cheque"
_MODE_BOTH = "Cash + Cheque"


class ChequeCustomerReceipt(Document):
    def validate(self):
        self.set_customer_account()
        self.set_company_currency_defaults()
        self.validate_required_fields()
        self.validate_cash_fields()
        self.validate_cheque_rows()
        self.validate_exchange_rate()
        self.calculate_totals()
        self.validate_no_duplicate_cheque_numbers()

    def before_submit(self):
        self.validate_cheque_settings_accounts()

    def on_submit(self):
        self.create_cash_payment_entry()
        self.create_cheque_registers_and_journal_entries()
        self.db_set("status", "Submitted")

    def on_cancel(self):
        self.cancel_cheque_accounting()
        self.db_set("status", "Cancelled")

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def set_customer_account(self):
        if self.company and self.customer:
            try:
                self.customer_account = get_customer_receivable_account(self.customer, self.company)
            except Exception:
                pass  # will fail on submit with a clear message

    def set_company_currency_defaults(self):
        if not self.currency and self.company:
            company_currency = frappe.db.get_value("Company", self.company, "default_currency")
            if company_currency:
                self.currency = company_currency
        if not self.posting_date:
            self.posting_date = today()

    def validate_required_fields(self):
        required = {"company": "Company", "posting_date": "Posting Date",
                    "customer": "Customer", "payment_mode": "Payment Mode", "currency": "Currency"}
        for field, label in required.items():
            if not self.get(field):
                frappe.throw(_("{0} is required.").format(frappe.bold(label)))

    def validate_cash_fields(self):
        if self.payment_mode not in (_MODE_CASH, _MODE_BOTH):
            return
        if not self.cash_account:
            frappe.throw(_("Cash / Bank Account is required when payment mode includes Cash."))
        if flt(self.cash_amount) <= 0:
            frappe.throw(_("Cash Amount must be greater than zero when payment mode includes Cash."))

    def validate_cheque_rows(self):
        if self.payment_mode not in (_MODE_CHEQUE, _MODE_BOTH):
            return
        if not self.cheques:
            frappe.throw(_("At least one cheque row is required when payment mode includes Cheque."))
        for idx, row in enumerate(self.cheques, 1):
            if not row.cheque_no:
                frappe.throw(_("Row {0}: Cheque No is required.").format(idx))
            if not row.bank:
                frappe.throw(_("Row {0}: Bank is required.").format(idx))
            if not row.due_date:
                frappe.throw(_("Row {0}: Due Date is required.").format(idx))
            if not row.currency:
                frappe.throw(_("Row {0}: Currency is required.").format(idx))
            if flt(row.amount) <= 0:
                frappe.throw(_("Row {0}: Amount must be greater than zero.").format(idx))
            if not row.exchange_rate or flt(row.exchange_rate) <= 0:
                frappe.throw(_("Row {0}: Exchange Rate is required and must be positive.").format(idx))
            row.base_amount = flt(row.amount) * flt(row.exchange_rate)

    def validate_exchange_rate(self):
        company_currency = frappe.db.get_value("Company", self.company, "default_currency") if self.company else None
        if not company_currency or not self.currency:
            return
        if self.currency == company_currency:
            self.exchange_rate = 1
        elif flt(self.exchange_rate) <= 0:
            frappe.throw(_("Exchange Rate is required when currency differs from company currency."))

    def calculate_totals(self):
        exchange_rate = flt(self.exchange_rate) or 1
        cash_amount = flt(self.cash_amount) if self.payment_mode in (_MODE_CASH, _MODE_BOTH) else 0
        cheque_amount = 0
        if self.payment_mode in (_MODE_CHEQUE, _MODE_BOTH):
            for row in self.cheques:
                cheque_amount += flt(row.amount)

        self.cash_amount = cash_amount
        self.cheque_amount = cheque_amount
        self.total_received_amount = cash_amount + cheque_amount
        self.base_cash_amount = cash_amount * exchange_rate
        self.base_cheque_amount = cheque_amount * exchange_rate
        self.base_total_received_amount = self.base_cash_amount + self.base_cheque_amount

    def validate_no_duplicate_cheque_numbers(self):
        if not self.cheques:
            return
        seen = {}
        for row in self.cheques:
            key = (row.cheque_no or "").strip().upper()
            if not key:
                continue
            if key in seen:
                frappe.throw(
                    _("Duplicate cheque number {0} in rows {1} and {2}.").format(
                        frappe.bold(row.cheque_no), seen[key], row.idx
                    )
                )
            seen[key] = row.idx

    def validate_cheque_settings_accounts(self):
        required = []
        if self.payment_mode in (_MODE_CHEQUE, _MODE_BOTH):
            required.append("cheques_receivable_in_hand_account")
        validate_cheque_settings(self.company, required)
        if not self.customer_account:
            self.customer_account = get_customer_receivable_account(self.customer, self.company)

    # ------------------------------------------------------------------
    # Submit: create accounting documents
    # ------------------------------------------------------------------

    def create_cash_payment_entry(self):
        if self.payment_mode not in (_MODE_CASH, _MODE_BOTH):
            return
        if flt(self.cash_amount) <= 0:
            return

        pe = make_payment_entry(
            company=self.company,
            posting_date=self.posting_date,
            payment_type="Receive",
            party_type="Customer",
            party=self.customer,
            party_account=self.customer_account,
            paid_from=self.customer_account,
            paid_to=self.cash_account,
            paid_amount=flt(self.cash_amount),
            ref_doctype="Cheque Customer Receipt",
            ref_name=self.name,
            remarks=_("Customer Receipt {0} - Cash from {1}").format(self.name, self.customer),
        )
        self.db_set("payment_entry", pe.name, update_modified=False)

    def create_cheque_registers_and_journal_entries(self):
        if self.payment_mode not in (_MODE_CHEQUE, _MODE_BOTH):
            return

        in_hand_account = get_cheques_in_hand_account(self.company)
        customer_account = self.customer_account or get_customer_receivable_account(
            self.customer, self.company
        )

        for row in self.cheques:
            cheque_register = self._create_cheque_register_for_row(row)
            je = self._create_cheque_receipt_journal_entry(row, cheque_register, in_hand_account, customer_account)

            frappe.db.set_value("Cheque Customer Receipt Cheque", row.name, {
                "cheque_register": cheque_register.name,
                "journal_entry": je.name,
            })
            frappe.db.set_value(_CHEQUE_REGISTER, cheque_register.name, {
                "customer_receipt": self.name,
                "linked_journal_entry": je.name,
            })

    def _create_cheque_register_for_row(self, row):
        cheque = frappe.new_doc(_CHEQUE_REGISTER)
        cheque.update({
            "company": self.company,
            "cheque_type": "Incoming",
            "cheque_number": row.cheque_no,
            "bank_name": row.bank,
            "bank_branch": row.branch or "",
            "due_date": row.due_date,
            "currency": row.currency,
            "amount": flt(row.amount),
            "exchange_rate": flt(row.exchange_rate) or 1,
            "party_type": "Customer",
            "party": self.customer,
            "customer_receipt": self.name,
        })
        cheque.insert(ignore_permissions=True)
        cheque.submit()
        return cheque

    def _create_cheque_receipt_journal_entry(self, row, cheque_register, in_hand_account, customer_account):
        amount = flt(row.amount)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {"account": in_hand_account, "debit_in_account_currency": amount},
                {
                    "account": customer_account,
                    "credit_in_account_currency": amount,
                    "party_type": "Customer",
                    "party": self.customer,
                },
            ],
            remarks=_("Customer Receipt {0} - Cheque No {1} from {2}").format(
                self.name, row.cheque_no, self.customer
            ),
            ref_doctype="Cheque Customer Receipt",
            ref_name=self.name,
        )

    # ------------------------------------------------------------------
    # Cancel: reverse all created accounting
    # ------------------------------------------------------------------

    def cancel_cheque_accounting(self):
        self._block_cancel_if_cheque_has_later_movements()
        self._cancel_cheque_journal_entries()
        self._cancel_cheque_registers()
        cancel_payment_entry(self.payment_entry, ignore_missing=True)

    def _block_cancel_if_cheque_has_later_movements(self):
        for row in self.cheques:
            if not row.cheque_register:
                continue
            movement_count = frappe.db.count(
                "Cheque Movement",
                {"cheque": row.cheque_register, "docstatus": 1},
            )
            if movement_count > 0:
                cheque_status = frappe.db.get_value(
                    _CHEQUE_REGISTER, row.cheque_register, "current_status"
                )
                frappe.throw(
                    _("Cannot cancel this receipt. Cheque No {0} ({1}) has later movements "
                      "and is currently in status {2}. Please cancel or reverse the cheque "
                      "movements first.").format(
                        frappe.bold(row.cheque_no),
                        frappe.bold(row.cheque_register),
                        frappe.bold(cheque_status),
                    )
                )

    def _cancel_cheque_journal_entries(self):
        for row in self.cheques:
            cancel_journal_entry(row.journal_entry, ignore_missing=True)

    def _cancel_cheque_registers(self):
        for row in self.cheques:
            if not row.cheque_register:
                continue
            cheque = frappe.get_doc(_CHEQUE_REGISTER, row.cheque_register)
            if cheque.docstatus == 1:
                cheque.flags.allow_direct_cancel = True
                cheque.cancel()
