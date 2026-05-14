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

MOVEMENT_TYPE_ALIASES = {
    "Deposit": "Deposit to Bank",
    "Clear": "Mark as Cleared",
    "Collected": "Mark as Cleared",
    "Return": "Mark as Returned",
    "Bounce": "Mark as Returned",
    "Cancel Cheque": "Cancel",
}

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

BANK_MOVEMENT_TYPES = {
    "Deposit to Bank",
    "Mark as Cleared",
    "Mark as Returned",
}

REASON_REQUIRED_MOVEMENT_TYPES = {
    "Mark as Returned",
    "Return to Customer",
    "Cancel",
}

SUPPLIER_REQUIRED_MOVEMENT_TYPES = {"Endorse to Supplier"}

EXCHANGE_DIFFERENCE_MOVEMENT_TYPES = {
    "Mark as Cleared",
}


def get_initial_status(cheque_type):
    if cheque_type == "Incoming":
        return INCOMING_INITIAL_STATUS
    if cheque_type == "Outgoing":
        return OUTGOING_INITIAL_STATUS
    return DRAFT_STATUS


def normalize_movement_type(movement_type):
    return MOVEMENT_TYPE_ALIASES.get(movement_type, movement_type)


def get_to_status(cheque_type, from_status, movement_type):
    movement_type = normalize_movement_type(movement_type)
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


def is_bank_movement(movement_type):
    return normalize_movement_type(movement_type) in BANK_MOVEMENT_TYPES


def requires_reason(movement_type):
    return normalize_movement_type(movement_type) in REASON_REQUIRED_MOVEMENT_TYPES


def requires_supplier(movement_type):
    return normalize_movement_type(movement_type) in SUPPLIER_REQUIRED_MOVEMENT_TYPES


def calculates_exchange_difference(movement_type):
    return normalize_movement_type(movement_type) in EXCHANGE_DIFFERENCE_MOVEMENT_TYPES
