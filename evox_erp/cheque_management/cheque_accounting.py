"""
Central accounting service for Phase 2 cheque management.

All accounting in this module goes through ERPNext Journal Entry or Payment Entry.
No raw GL Entries are written directly.
All accounts are read from Cheque Settings — nothing is hardcoded.
"""

import frappe
from frappe import _
from frappe.utils import flt


# ---------------------------------------------------------------------------
# Cheque Settings helpers
# ---------------------------------------------------------------------------

def get_cheque_settings(company=None):
    """Return the Cheque Settings doc.  Throw if the record does not exist."""
    try:
        settings = frappe.get_single("Cheque Settings")
    except Exception:
        frappe.throw(_("Cheque Settings has not been configured. Please configure it before proceeding."))
    return settings


def validate_cheque_settings(company, required_fields=None):
    """
    Validate that all required account fields are populated in Cheque Settings.

    required_fields: list of fieldnames to check.  If None, checks the six
    core account fields that almost every accounting flow needs.
    """
    if required_fields is None:
        required_fields = [
            "cheques_receivable_in_hand_account",
            "cheques_under_collection_account",
            "returned_cheques_receivable_account",
            "post_dated_cheques_payable_account",
            "bank_charges_account",
            "default_bank_account",
        ]

    settings = get_cheque_settings(company)
    missing = []
    for fieldname in required_fields:
        if not settings.get(fieldname):
            label = frappe.get_meta("Cheque Settings").get_label(fieldname)
            missing.append(label)

    if missing:
        frappe.throw(
            _("The following accounts are not configured in Cheque Settings: {0}").format(
                ", ".join(frappe.bold(m) for m in missing)
            )
        )


# ---------------------------------------------------------------------------
# Individual account getters (each validates the account exists)
# ---------------------------------------------------------------------------

def _get_settings_account(fieldname, company=None):
    settings = get_cheque_settings(company)
    account = settings.get(fieldname)
    if not account:
        label = frappe.get_meta("Cheque Settings").get_label(fieldname)
        frappe.throw(
            _("{0} is not configured in Cheque Settings.").format(frappe.bold(label))
        )
    return account


def get_cheques_in_hand_account(company=None):
    return _get_settings_account("cheques_receivable_in_hand_account", company)


def get_cheques_under_collection_account(company=None):
    return _get_settings_account("cheques_under_collection_account", company)


def get_returned_cheques_account(company=None):
    return _get_settings_account("returned_cheques_receivable_account", company)


def get_post_dated_cheques_payable_account(company=None):
    return _get_settings_account("post_dated_cheques_payable_account", company)


def get_bank_charges_account(company=None):
    return _get_settings_account("bank_charges_account", company)


def get_default_bank_account(company=None):
    return _get_settings_account("default_bank_account", company)


# ---------------------------------------------------------------------------
# Party account helpers (via ERPNext standard logic)
# ---------------------------------------------------------------------------

def get_customer_receivable_account(customer, company):
    """Return the default receivable account for a customer in the given company."""
    if not (customer and company):
        frappe.throw(_("Customer and Company are required to resolve the receivable account."))
    try:
        from erpnext.accounts.party import get_party_account
        account = get_party_account("Customer", customer, company)
    except Exception as e:
        frappe.throw(
            _("Could not resolve receivable account for customer {0} in company {1}: {2}").format(
                frappe.bold(customer), frappe.bold(company), str(e)
            )
        )
    if not account:
        frappe.throw(
            _("No receivable account found for customer {0} in company {1}. "
              "Please configure the customer's account in Accounts Receivable settings.").format(
                frappe.bold(customer), frappe.bold(company)
            )
        )
    return account


def get_supplier_payable_account(supplier, company):
    """Return the default payable account for a supplier in the given company."""
    if not (supplier and company):
        frappe.throw(_("Supplier and Company are required to resolve the payable account."))
    try:
        from erpnext.accounts.party import get_party_account
        account = get_party_account("Supplier", supplier, company)
    except Exception as e:
        frappe.throw(
            _("Could not resolve payable account for supplier {0} in company {1}: {2}").format(
                frappe.bold(supplier), frappe.bold(company), str(e)
            )
        )
    if not account:
        frappe.throw(
            _("No payable account found for supplier {0} in company {1}. "
              "Please configure the supplier's account in Accounts Payable settings.").format(
                frappe.bold(supplier), frappe.bold(company)
            )
        )
    return account


def get_party_account_for_cheque(party_type, party, company):
    """Dispatch to customer or supplier account getter based on party_type."""
    if party_type == "Customer":
        return get_customer_receivable_account(party, company)
    if party_type == "Supplier":
        return get_supplier_payable_account(party, company)
    frappe.throw(_("Unsupported party type: {0}").format(frappe.bold(party_type)))


def get_exchange_gain_loss_account(company):
    """Return the exchange gain/loss account configured on the Company master."""
    if not company:
        frappe.throw(_("Company is required to resolve the exchange gain/loss account."))
    account = frappe.db.get_value("Company", company, "exchange_gain_loss_account")
    if not account:
        frappe.throw(
            _("Exchange Gain / Loss account is not configured on company {0}. "
              "Please configure it in the Company master.").format(frappe.bold(company))
        )
    return account


# ---------------------------------------------------------------------------
# Journal Entry factory
# ---------------------------------------------------------------------------

def make_journal_entry(company, posting_date, accounts, remarks,
                       ref_doctype=None, ref_name=None):
    """
    Create and submit a Journal Entry.

    accounts: list of dicts, each containing:
      - account (str, required)
      - debit_in_account_currency (float, default 0)
      - credit_in_account_currency (float, default 0)
      - party_type (str, optional)
      - party (str, optional)
      - cost_center (str, optional)
      - exchange_rate (float, optional, default 1)
      - account_currency (str, optional)

    Returns the submitted Journal Entry document.
    """
    if not accounts:
        frappe.throw(_("Journal Entry requires at least one account row."))

    je = frappe.new_doc("Journal Entry")
    je.company = company
    je.posting_date = posting_date
    je.voucher_type = "Journal Entry"
    je.user_remark = remarks or ""

    if ref_doctype and ref_name:
        je.cheque_no = ref_name
        je.cheque_date = posting_date

    for row in accounts:
        entry = {
            "account": row["account"],
            "debit_in_account_currency": flt(row.get("debit_in_account_currency", 0)),
            "credit_in_account_currency": flt(row.get("credit_in_account_currency", 0)),
        }
        if row.get("party_type"):
            entry["party_type"] = row["party_type"]
        if row.get("party"):
            entry["party"] = row["party"]
        if row.get("exchange_rate"):
            entry["exchange_rate"] = flt(row["exchange_rate"])
        if row.get("account_currency"):
            entry["account_currency"] = row["account_currency"]
        if row.get("cost_center"):
            entry["cost_center"] = row["cost_center"]

        je.append("accounts", entry)

    je.insert(ignore_permissions=True)
    je.submit()
    return je


# ---------------------------------------------------------------------------
# Payment Entry factory
# ---------------------------------------------------------------------------

def make_payment_entry(company, posting_date, payment_type, party_type, party,
                       party_account, paid_from, paid_to, paid_amount,
                       source_exchange_rate=1, target_exchange_rate=1,
                       source_amount=None, ref_doctype=None, ref_name=None,
                       remarks=None):
    """
    Create and submit a Payment Entry.

    payment_type: "Receive" (customer pays us) or "Pay" (we pay supplier).
    paid_from / paid_to: account names.
    paid_amount: amount in the payment currency.
    """
    pe = frappe.new_doc("Payment Entry")
    pe.company = company
    pe.posting_date = posting_date
    pe.payment_type = payment_type
    pe.party_type = party_type
    pe.party = party
    pe.party_account = party_account
    pe.paid_from = paid_from
    pe.paid_to = paid_to
    pe.paid_amount = flt(paid_amount)
    pe.received_amount = flt(paid_amount)
    pe.source_exchange_rate = flt(source_exchange_rate) or 1
    pe.target_exchange_rate = flt(target_exchange_rate) or 1
    if source_amount:
        pe.paid_amount = flt(source_amount)

    if remarks:
        pe.remarks = remarks

    if ref_doctype and ref_name:
        pe.append("references", {
            "reference_doctype": ref_doctype,
            "reference_name": ref_name,
            "allocated_amount": flt(paid_amount),
        })

    pe.insert(ignore_permissions=True)
    pe.submit()
    return pe


# ---------------------------------------------------------------------------
# Holding account resolver
# ---------------------------------------------------------------------------

def get_holding_account_for_status(cheque_status, company=None):
    """
    Return the GL account that currently holds the cheque value based on its
    current_status.  Used to determine the credit side of movement entries.
    """
    status_map = {
        "Received / In Hand": get_cheques_in_hand_account,
        "Deposited / Under Collection": get_cheques_under_collection_account,
        "Returned": get_returned_cheques_account,
    }
    getter = status_map.get(cheque_status)
    if getter:
        return getter(company)
    # For Endorsed to Supplier the cheque is in the supplier payable — caller must
    # resolve this separately using the cheque's endorsed_to_supplier field.
    return None


# ---------------------------------------------------------------------------
# Cancel / reverse helper
# ---------------------------------------------------------------------------

def cancel_journal_entry(journal_entry_name, ignore_missing=False):
    """
    Cancel a submitted Journal Entry by name.
    If ignore_missing=True, silently returns None when the JE does not exist.
    """
    if not journal_entry_name:
        return
    if not frappe.db.exists("Journal Entry", journal_entry_name):
        if ignore_missing:
            return
        frappe.throw(_("Journal Entry {0} not found.").format(frappe.bold(journal_entry_name)))

    je = frappe.get_doc("Journal Entry", journal_entry_name)
    if je.docstatus == 1:
        je.cancel()
    elif je.docstatus == 2:
        pass  # already cancelled
    elif je.docstatus == 0:
        je.delete()


def cancel_payment_entry(payment_entry_name, ignore_missing=False):
    """Cancel a submitted Payment Entry by name."""
    if not payment_entry_name:
        return
    if not frappe.db.exists("Payment Entry", payment_entry_name):
        if ignore_missing:
            return
        frappe.throw(_("Payment Entry {0} not found.").format(frappe.bold(payment_entry_name)))

    pe = frappe.get_doc("Payment Entry", payment_entry_name)
    if pe.docstatus == 1:
        pe.cancel()
    elif pe.docstatus == 2:
        pass  # already cancelled
