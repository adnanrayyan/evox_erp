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
from evox_erp.cheque_management.cheque_accounting import (
    cancel_journal_entry,
    get_cheques_in_hand_account,
    get_cheques_under_collection_account,
    get_exchange_gain_loss_account,
    get_party_account_for_cheque,
    get_post_dated_cheques_payable_account,
    get_supplier_payable_account,
    make_journal_entry,
)

# ---------------------------------------------------------------------------
# Module-level constants — avoids repeated string literals
# ---------------------------------------------------------------------------
_CHEQUE_REGISTER = "Cheque Register"
_CHEQUE_MOVEMENT = "Cheque Movement"
_DEPOSIT = "Deposit to Bank"
_CLEARED = "Mark as Cleared"
_RETURNED = "Mark as Returned"
_ENDORSE = "Endorse to Supplier"
_RETURN_TO_CUSTOMER = "Return to Customer"
_CANCEL = "Cancel"

_STATUS_IN_HAND = "Received / In Hand"
_STATUS_UNDER_COLLECTION = "Deposited / Under Collection"
_STATUS_ENDORSED = "Endorsed to Supplier"
_STATUS_RETURNED = "Returned"


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
        self.cancel_movement_journal_entry()

    # ------------------------------------------------------------------
    # Cheque data helpers
    # ------------------------------------------------------------------

    def get_cheque(self):
        if not self.cheque:
            frappe.throw(_("Cheque is required."))
        return frappe.get_doc(_CHEQUE_REGISTER, self.cheque)

    def set_defaults_from_cheque(self):
        if not self.cheque:
            return

        cheque = frappe.get_doc(_CHEQUE_REGISTER, self.cheque)
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

        same_currency = cheque.currency == self.company_currency
        no_exchange_calc = not calculates_exchange_difference(self.movement_type)
        rate_not_set = flt(self.movement_exchange_rate) <= 0

        # Set movement_exchange_rate to original when: same currency, non-exchange movement,
        # or user hasn't entered a rate yet.
        if same_currency or no_exchange_calc or rate_not_set:
            self.movement_exchange_rate = original_exchange_rate

        movement_exchange_rate = flt(self.movement_exchange_rate) or 1
        self.movement_base_amount = flt(cheque.amount) * movement_exchange_rate

        if same_currency or no_exchange_calc:
            self.exchange_difference = 0
        else:
            self.exchange_difference = flt(self.movement_base_amount) - flt(self.original_base_amount)

        self.exchange_difference_type = get_exchange_difference_type(self.exchange_difference)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Cheque Register update on submit
    # ------------------------------------------------------------------

    def update_cheque_register(self):
        cheque = self.get_cheque()
        movement_type = normalize_movement_type(self.movement_type)
        cheque.flags.allow_status_update = True
        cheque.current_status = self.to_status
        cheque.current_movement = self.name

        if movement_type == _DEPOSIT:
            cheque.deposit_bank_account = self.bank_account
            cheque.deposit_date = self.posting_date
        elif movement_type == _CLEARED:
            cheque.clearance_date = self.posting_date
        elif movement_type == _RETURNED:
            cheque.return_date = self.posting_date
            cheque.return_reason = self.reason
        elif movement_type == _ENDORSE:
            cheque.endorsed_to_supplier = self.supplier
            cheque.endorsed_date = self.posting_date

        cheque.save(ignore_permissions=True)
        cheque.add_comment(
            "Comment",
            _("Cheque movement {0}: {1} → {2}.").format(
                frappe.bold(self.movement_type),
                frappe.bold(self.from_status),
                frappe.bold(self.to_status),
            ),
        )

    # ------------------------------------------------------------------
    # Accounting entry creation — dispatches by cheque type and movement
    # ------------------------------------------------------------------

    def create_accounting_entry_for_movement(self):
        """
        Create the Journal Entry for this lifecycle movement.
        Reads all accounts from Cheque Settings or ERPNext party defaults.
        No raw GL entries are written directly.
        """
        cheque = self.get_cheque()
        movement_type = normalize_movement_type(self.movement_type)
        cheque_type = frappe.db.get_value(_CHEQUE_REGISTER, self.cheque, "cheque_type")

        if cheque_type == "Incoming":
            je = self._je_incoming(cheque, movement_type)
        elif cheque_type == "Outgoing":
            je = self._je_outgoing(cheque, movement_type)
        else:
            return

        if je:
            self.db_set("journal_entry", je.name, update_modified=False)
            self.db_set("accounting_posted", 1, update_modified=False)
            cheque.flags.allow_status_update = True
            frappe.db.set_value(_CHEQUE_REGISTER, self.cheque, "linked_journal_entry", je.name)

    # ------------------------------------------------------------------
    # Incoming cheque JE builders
    # ------------------------------------------------------------------

    def _je_incoming(self, cheque, movement_type):
        if movement_type == _DEPOSIT:
            return self._je_deposit(cheque)
        if movement_type == _CLEARED:
            return self._je_cleared_incoming(cheque)
        if movement_type == _RETURNED:
            return self._je_returned_incoming(cheque)
        if movement_type == _ENDORSE:
            return self._je_endorse(cheque)
        if movement_type == _CANCEL:
            return self._je_cancel_incoming(cheque)
        # Return to Customer — physical handback, no accounting entry needed
        return None

    def _je_deposit(self, cheque):
        in_hand = get_cheques_in_hand_account(self.company)
        under_collection = get_cheques_under_collection_account(self.company)
        amount = flt(cheque.amount)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {"account": under_collection, "debit_in_account_currency": amount},
                {"account": in_hand, "credit_in_account_currency": amount},
            ],
            remarks=_("Deposit Cheque {0} to bank").format(cheque.cheque_number),
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    def _je_cleared_incoming(self, cheque):
        under_collection = get_cheques_under_collection_account(self.company)
        original_base = flt(self.original_base_amount) or flt(cheque.amount)
        movement_base = flt(self.movement_base_amount) or flt(cheque.amount)
        accounts = [
            {"account": self.bank_account, "debit_in_account_currency": movement_base},
            {"account": under_collection, "credit_in_account_currency": original_base},
        ]
        self._append_exchange_diff_rows(accounts)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=accounts,
            remarks=_("Cheque {0} cleared from bank").format(cheque.cheque_number),
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    def _je_returned_incoming(self, cheque):
        party_account = get_party_account_for_cheque(cheque.party_type, cheque.party, self.company)
        amount = flt(cheque.amount)
        from_status = self.from_status

        if from_status == _STATUS_UNDER_COLLECTION:
            holding = get_cheques_under_collection_account(self.company)
            remarks = _("Cheque {0} returned from bank").format(cheque.cheque_number)
        elif from_status == _STATUS_IN_HAND:
            holding = get_cheques_in_hand_account(self.company)
            remarks = _("Cheque {0} returned while in hand").format(cheque.cheque_number)
        elif from_status == _STATUS_ENDORSED:
            return self._je_returned_from_endorsed(cheque, party_account, amount)
        else:
            return None

        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {
                    "account": party_account,
                    "debit_in_account_currency": amount,
                    "party_type": cheque.party_type,
                    "party": cheque.party,
                },
                {"account": holding, "credit_in_account_currency": amount},
            ],
            remarks=remarks,
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    def _je_returned_from_endorsed(self, cheque, party_account, amount):
        """Cheque returned by supplier: Dr Customer Receivable / Cr Supplier Payable."""
        supplier = frappe.db.get_value(_CHEQUE_REGISTER, self.cheque, "endorsed_to_supplier")
        if not supplier:
            frappe.throw(
                _("Cannot determine endorsed supplier for cheque {0}. "
                  "The endorsed_to_supplier field is not set.").format(cheque.cheque_number)
            )
        supplier_account = get_supplier_payable_account(supplier, self.company)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {
                    "account": party_account,
                    "debit_in_account_currency": amount,
                    "party_type": cheque.party_type,
                    "party": cheque.party,
                },
                {
                    "account": supplier_account,
                    "credit_in_account_currency": amount,
                    "party_type": "Supplier",
                    "party": supplier,
                },
            ],
            remarks=_("Cheque {0} returned by supplier {1}").format(cheque.cheque_number, supplier),
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    def _je_endorse(self, cheque):
        in_hand = get_cheques_in_hand_account(self.company)
        supplier_account = get_supplier_payable_account(self.supplier, self.company)
        original_base = flt(self.original_base_amount) or flt(cheque.amount)
        movement_base = flt(self.movement_base_amount) or flt(cheque.amount)
        accounts = [
            {
                "account": supplier_account,
                "debit_in_account_currency": movement_base,
                "party_type": "Supplier",
                "party": self.supplier,
            },
            {"account": in_hand, "credit_in_account_currency": original_base},
        ]
        self._append_exchange_diff_rows(accounts)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=accounts,
            remarks=_("Cheque {0} endorsed to supplier {1}").format(
                cheque.cheque_number, self.supplier
            ),
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    def _je_cancel_incoming(self, cheque):
        party_account = get_party_account_for_cheque(cheque.party_type, cheque.party, self.company)
        amount = flt(cheque.amount)
        from_status = self.from_status

        if from_status == _STATUS_IN_HAND:
            holding = get_cheques_in_hand_account(self.company)
            remarks = _("Cheque {0} cancelled from In Hand").format(cheque.cheque_number)
            return self._simple_cancel_je(party_account, cheque, holding, amount, remarks)

        if from_status == _STATUS_UNDER_COLLECTION:
            holding = get_cheques_under_collection_account(self.company)
            remarks = _("Cheque {0} cancelled from Under Collection").format(cheque.cheque_number)
            return self._simple_cancel_je(party_account, cheque, holding, amount, remarks)

        if from_status == _STATUS_ENDORSED:
            return self._je_cancel_endorsed(cheque, party_account, amount)

        # Cancel from "Returned" — customer receivable already restored by the return movement
        return None

    def _simple_cancel_je(self, party_account, cheque, holding_account, amount, remarks):
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {
                    "account": party_account,
                    "debit_in_account_currency": amount,
                    "party_type": cheque.party_type,
                    "party": cheque.party,
                },
                {"account": holding_account, "credit_in_account_currency": amount},
            ],
            remarks=remarks,
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    def _je_cancel_endorsed(self, cheque, party_account, amount):
        supplier = frappe.db.get_value(_CHEQUE_REGISTER, self.cheque, "endorsed_to_supplier")
        if not supplier:
            frappe.throw(
                _("Cannot determine endorsed supplier to cancel endorsed cheque {0}.").format(
                    cheque.cheque_number
                )
            )
        supplier_account = get_supplier_payable_account(supplier, self.company)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {
                    "account": party_account,
                    "debit_in_account_currency": amount,
                    "party_type": cheque.party_type,
                    "party": cheque.party,
                },
                {
                    "account": supplier_account,
                    "credit_in_account_currency": amount,
                    "party_type": "Supplier",
                    "party": supplier,
                },
            ],
            remarks=_("Cheque {0} cancelled (was endorsed to supplier {1})").format(
                cheque.cheque_number, supplier
            ),
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    # ------------------------------------------------------------------
    # Outgoing cheque JE builders
    # ------------------------------------------------------------------

    def _je_outgoing(self, cheque, movement_type):
        if movement_type == _CLEARED:
            return self._je_cleared_outgoing(cheque)
        if movement_type == _CANCEL:
            return self._je_cancel_outgoing(cheque)
        return None

    def _je_cleared_outgoing(self, cheque):
        post_dated_payable = get_post_dated_cheques_payable_account(self.company)
        original_base = flt(self.original_base_amount) or flt(cheque.amount)
        movement_base = flt(self.movement_base_amount) or flt(cheque.amount)
        accounts = [
            {"account": post_dated_payable, "debit_in_account_currency": original_base},
            {"account": self.bank_account, "credit_in_account_currency": movement_base},
        ]
        self._append_exchange_diff_rows(accounts)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=accounts,
            remarks=_("Outgoing Cheque {0} cleared from bank").format(cheque.cheque_number),
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    def _je_cancel_outgoing(self, cheque):
        post_dated_payable = get_post_dated_cheques_payable_account(self.company)
        party_account = get_party_account_for_cheque(cheque.party_type, cheque.party, self.company)
        amount = flt(cheque.amount)
        return make_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
            accounts=[
                {"account": post_dated_payable, "debit_in_account_currency": amount},
                {
                    "account": party_account,
                    "credit_in_account_currency": amount,
                    "party_type": cheque.party_type,
                    "party": cheque.party,
                },
            ],
            remarks=_("Outgoing Cheque {0} cancelled").format(cheque.cheque_number),
            ref_doctype=_CHEQUE_MOVEMENT,
            ref_name=self.name,
        )

    # ------------------------------------------------------------------
    # Exchange difference helper
    # ------------------------------------------------------------------

    def _append_exchange_diff_rows(self, accounts):
        """Append a gain/loss row to accounts if an exchange difference exists."""
        exchange_diff = flt(self.exchange_difference)
        if exchange_diff == 0:
            return
        gain_loss_account = get_exchange_gain_loss_account(self.company)
        if exchange_diff > 0:
            accounts.append({"account": gain_loss_account, "credit_in_account_currency": exchange_diff})
        else:
            accounts.append({"account": gain_loss_account, "debit_in_account_currency": abs(exchange_diff)})

    # ------------------------------------------------------------------
    # Cancel / status restore
    # ------------------------------------------------------------------

    def validate_latest_movement_for_cancel(self):
        latest = frappe.get_all(
            _CHEQUE_MOVEMENT,
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

        previous = frappe.get_all(
            _CHEQUE_MOVEMENT,
            filters={"cheque": self.cheque, "docstatus": 1, "name": ["!=", self.name]},
            fields=["name"],
            order_by="creation desc, name desc",
            limit=1,
        )
        cheque.current_movement = previous[0].name if previous else None

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
        if movement_type == _DEPOSIT:
            if cheque.deposit_bank_account == self.bank_account:
                cheque.deposit_bank_account = None
            if str(cheque.deposit_date or "") == str(self.posting_date or ""):
                cheque.deposit_date = None
        elif movement_type == _CLEARED:
            if str(cheque.clearance_date or "") == str(self.posting_date or ""):
                cheque.clearance_date = None
        elif movement_type == _RETURNED:
            if str(cheque.return_date or "") == str(self.posting_date or ""):
                cheque.return_date = None
            if cheque.return_reason == self.reason:
                cheque.return_reason = None
        elif movement_type == _ENDORSE:
            if cheque.endorsed_to_supplier == self.supplier:
                cheque.endorsed_to_supplier = None
            if str(cheque.endorsed_date or "") == str(self.posting_date or ""):
                cheque.endorsed_date = None

    def cancel_movement_journal_entry(self):
        if self.journal_entry:
            cancel_journal_entry(self.journal_entry, ignore_missing=True)
            self.db_set("accounting_posted", 0, update_modified=False)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

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
    cheque_doc = frappe.get_doc(_CHEQUE_REGISTER, cheque)
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
