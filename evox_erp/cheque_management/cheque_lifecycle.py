import frappe
from frappe import _


DRAFT_STATUS = "Draft"
INCOMING_INITIAL_STATUS = "Received / In Hand"
OUTGOING_INITIAL_STATUS = "Issued"

FINAL_STATUSES = {
    "Cleared",
    "Returned to Customer",
    "Endorsed to Supplier",
    "Cancelled",
    "Reversed",
}

INACTIVE_STATUSES = {"Cancelled", "Reversed"}

VALID_TRANSITIONS = {
    "Incoming": {
        ("Received / In Hand", "Deposit to Bank"): "Deposited / Under Collection",
        ("Received / In Hand", "Endorse to Supplier"): "Endorsed to Supplier",
        ("Received / In Hand", "Return to Customer"): "Returned to Customer",
        ("Received / In Hand", "Cancel"): "Cancelled",
        ("Deposited / Under Collection", "Mark as Cleared"): "Cleared",
        ("Deposited / Under Collection", "Mark as Returned"): "Returned",
        ("Returned", "Return to Customer"): "Returned to Customer",
        ("Returned", "Cancel"): "Cancelled",
    },
    "Outgoing": {
        ("Issued", "Mark as Cleared"): "Cleared",
        ("Issued", "Cancel"): "Cancelled",
        ("Issued", "Reverse"): "Reversed",
    },
}


def get_initial_status(cheque_type):
    if cheque_type == "Incoming":
        return INCOMING_INITIAL_STATUS
    if cheque_type == "Outgoing":
        return OUTGOING_INITIAL_STATUS
    return DRAFT_STATUS


def get_to_status(cheque_type, from_status, movement_type):
    transition_map = VALID_TRANSITIONS.get(cheque_type) or {}
    to_status = transition_map.get((from_status, movement_type))
    if not to_status:
        frappe.throw(
            _("{0} movement is not allowed for a {1} cheque currently in status {2}.").format(
                frappe.bold(movement_type),
                frappe.bold(cheque_type or ""),
                frappe.bold(from_status or ""),
            )
        )
    return to_status


def is_inactive_status(status):
    return status in INACTIVE_STATUSES

