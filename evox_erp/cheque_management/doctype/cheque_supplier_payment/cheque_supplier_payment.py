import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from evox_erp.cheque_management.cheque_accounting import (
    cancel_payment_entry,
    get_cheques_in_hand_account,
    get_supplier_payable_account,
    make_payment_entry,
    validate_cheque_settings,
)

_CHEQUE_REGISTER = "Cheque Register"
_CHEQUE_MOVEMENT = "Cheque Movement"
_STATUS_IN_HAND = "Received / In Hand"
_MODE_CASH = "Cash"
_MODE_CHEQUE = "Cheque"
_MODE_BOTH = "Cash + Cheque"


class ChequeSupplierPayment(Document):
    def validate(self):
        self.set_supplier_account()
        self.set_company_currency_defaults()
        self.validate_required_fields()
        self.validate_cash_fields()
        self.validate_cheque_rows()
        self.validate_exchange_rate()
        self.validate_no_duplicate_cheques()
        self.calculate_totals()

    def before_submit(self):
        self.validate_cheque_settings_accounts()
        self.validate_cheques_still_available()

    def on_submit(self):
        self.create_cash_payment_entry()
        self.create_cheque_endorsements()
        self.db_set("status", "Submitted")

    def on_cancel(self):
        cancel_payment_entry(self.payment_entry, ignore_missing=True)
        self.cancel_endorsement_movements()
        self.db_set("status", "Cancelled")

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def set_supplier_account(self):
        if self.company and self.supplier:
            try:
                self.supplier_account = get_supplier_payable_account(self.supplier, self.company)
            except Exception:
                pass

    def set_company_currency_defaults(self):
        if not self.currency and self.company:
            company_currency = frappe.db.get_value("Company", self.company, "default_currency")
            if company_currency:
                self.currency = company_currency
        if not self.posting_date:
            self.posting_date = today()

    def validate_required_fields(self):
        required = {"company": "Company", "posting_date": "Posting Date",
                    "supplier": "Supplier", "payment_mode": "Payment Mode", "currency": "Currency"}
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
            if not row.cheque_register:
                frappe.throw(_("Row {0}: Cheque Register is required.").format(idx))

    def validate_exchange_rate(self):
        if not self.company or not self.currency:
            return
        company_currency = frappe.db.get_value("Company", self.company, "default_currency")
        if self.currency == company_currency:
            self.exchange_rate = 1
        elif flt(self.exchange_rate) <= 0:
            frappe.throw(_("Exchange Rate is required when currency differs from company currency."))

    def validate_no_duplicate_cheques(self):
        if not self.cheques:
            return
        seen = {}
        for row in self.cheques:
            key = row.cheque_register or ""
            if not key:
                continue
            if key in seen:
                frappe.throw(
                    _("Cheque {0} is selected in both row {1} and row {2}.").format(
                        frappe.bold(key), seen[key], row.idx
                    )
                )
            seen[key] = row.idx

    def calculate_totals(self):
        exchange_rate = flt(self.exchange_rate) or 1
        cash_amount = flt(self.cash_amount) if self.payment_mode in (_MODE_CASH, _MODE_BOTH) else 0
        cheque_amount = 0
        if self.payment_mode in (_MODE_CHEQUE, _MODE_BOTH):
            for row in self.cheques:
                cheque_amount += flt(row.amount)

        self.cash_amount = cash_amount
        self.cheque_amount = cheque_amount
        self.total_paid_amount = cash_amount + cheque_amount
        self.base_cash_amount = cash_amount * exchange_rate
        self.base_cheque_amount = cheque_amount * exchange_rate
        self.base_total_paid_amount = self.base_cash_amount + self.base_cheque_amount

    def validate_cheque_settings_accounts(self):
        required = []
        if self.payment_mode in (_MODE_CHEQUE, _MODE_BOTH):
            required.append("cheques_receivable_in_hand_account")
        validate_cheque_settings(self.company, required)
        if not self.supplier_account:
            self.supplier_account = get_supplier_payable_account(self.supplier, self.company)

    def validate_cheques_still_available(self):
        """Re-check availability at submit time to prevent race conditions."""
        for row in self.cheques:
            if not row.cheque_register:
                continue
            current_status, company, cheque_type = frappe.db.get_value(
                _CHEQUE_REGISTER,
                row.cheque_register,
                ["current_status", "company", "cheque_type"],
            )
            if company != self.company:
                frappe.throw(
                    _("Cheque {0} belongs to a different company and cannot be used here.").format(
                        frappe.bold(row.cheque_register)
                    )
                )
            if cheque_type != "Incoming":
                frappe.throw(
                    _("Cheque {0} is not an incoming cheque and cannot be endorsed to a supplier.").format(
                        frappe.bold(row.cheque_register)
                    )
                )
            if current_status != _STATUS_IN_HAND:
                frappe.throw(
                    _("Cheque {0} is no longer available (current status: {1}). "
                      "Only cheques with status '{2}' can be used.").format(
                        frappe.bold(row.cheque_register),
                        frappe.bold(current_status),
                        frappe.bold(_STATUS_IN_HAND),
                    )
                )
            # Check not already used in another submitted payment
            conflict = frappe.db.sql("""
                SELECT csp.name
                FROM `tabCheque Supplier Payment Cheque` cspc
                JOIN `tabCheque Supplier Payment` csp ON csp.name = cspc.parent
                WHERE cspc.cheque_register = %s
                  AND csp.docstatus = 1
                  AND csp.name != %s
            """, (row.cheque_register, self.name or ""), as_dict=True)
            if conflict:
                frappe.throw(
                    _("Cheque {0} is already used in submitted supplier payment {1}.").format(
                        frappe.bold(row.cheque_register), frappe.bold(conflict[0].name)
                    )
                )

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def create_cash_payment_entry(self):
        if self.payment_mode not in (_MODE_CASH, _MODE_BOTH):
            return
        if flt(self.cash_amount) <= 0:
            return

        pe = make_payment_entry(
            company=self.company,
            posting_date=self.posting_date,
            payment_type="Pay",
            party_type="Supplier",
            party=self.supplier,
            party_account=self.supplier_account,
            paid_from=self.cash_account,
            paid_to=self.supplier_account,
            paid_amount=flt(self.cash_amount),
            ref_doctype="Cheque Supplier Payment",
            ref_name=self.name,
            remarks=_("Supplier Payment {0} - Cash to {1}").format(self.name, self.supplier),
        )
        self.db_set("payment_entry", pe.name, update_modified=False)

    def create_cheque_endorsements(self):
        if self.payment_mode not in (_MODE_CHEQUE, _MODE_BOTH):
            return

        for row in self.cheques:
            movement = self._endorse_cheque(row)
            je_name = frappe.db.get_value(_CHEQUE_MOVEMENT, movement.name, "journal_entry")
            frappe.db.set_value("Cheque Supplier Payment Cheque", row.name, {
                "movement": movement.name,
                "journal_entry": je_name,
                "current_status": "Endorsed to Supplier",
            })
            frappe.db.set_value(_CHEQUE_REGISTER, row.cheque_register, {
                "supplier_payment": self.name,
            })

    def _endorse_cheque(self, row):
        from evox_erp.cheque_management.doctype.cheque_register.cheque_register import endorse_to_supplier
        result = endorse_to_supplier(
            cheque_name=row.cheque_register,
            supplier=self.supplier,
            posting_date=self.posting_date,
            notes=_("Endorsed via Supplier Payment {0}").format(self.name),
        )
        movement = frappe.get_doc(_CHEQUE_MOVEMENT, result["movement"])
        frappe.db.set_value(_CHEQUE_MOVEMENT, movement.name, {
            "supplier_payment": self.name,
        })
        return movement

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_endorsement_movements(self):
        """Cancel endorsement movements in reverse order to safely restore cheque statuses."""
        rows_with_movements = [r for r in self.cheques if r.movement]
        for row in reversed(rows_with_movements):
            movement = frappe.get_doc(_CHEQUE_MOVEMENT, row.movement)
            if movement.docstatus == 1:
                movement.cancel()


@frappe.whitelist()
def get_available_cheques(company):
    """Return cheques available for supplier payment selection."""
    if not company:
        return []

    used_in_payment = frappe.db.sql_list("""
        SELECT cspc.cheque_register
        FROM `tabCheque Supplier Payment Cheque` cspc
        JOIN `tabCheque Supplier Payment` csp ON csp.name = cspc.parent
        WHERE csp.docstatus = 1
          AND cspc.cheque_register IS NOT NULL
    """)

    filters = {
        "docstatus": 1,
        "cheque_type": "Incoming",
        "current_status": _STATUS_IN_HAND,
        "company": company,
    }
    if used_in_payment:
        filters["name"] = ["not in", used_in_payment]

    cheques = frappe.get_all(
        _CHEQUE_REGISTER,
        filters=filters,
        fields=["name", "cheque_number", "party", "bank_name", "due_date",
                "amount", "currency", "exchange_rate", "base_amount", "current_status"],
    )
    return cheques
