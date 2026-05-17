import frappe
from frappe import _


DRAFT_STATUS = "Draft"
INCOMING_INITIAL_STATUS = "Received / In Hand"
OUTGOING_INITIAL_STATUS = "Issued"

FINAL_STATUSES = {
    "Cleared",
    "Returned",
    "Endorsed to Supplier",
    "Cancelled",
    "Reversed",
    # legacy status kept so existing records display without error
    "Returned to Customer",
}

INACTIVE_STATUSES = {"Cancelled", "Reversed"}

MOVEMENT_TYPE_ALIASES = {
    "Deposit": "Deposit to Bank",
    "Clear": "Mark as Cleared",
    "Collected": "Mark as Cleared",
    "Return": "Mark as Returned",
    "Bounce": "Mark as Returned",
    # "Return to Customer" was a legacy movement type; normalise to Mark as Returned
    "Return to Customer": "Mark as Returned",
    "Cancel Cheque": "Cancel",
}

VALID_TRANSITIONS = {
    "Incoming": {
        ("Received / In Hand", "Deposit to Bank"): "Deposited / Under Collection",
        ("Received / In Hand", "Endorse to Supplier"): "Endorsed to Supplier",
        # Allow direct return from hand (cheque never deposited, e.g. customer recall)
        ("Received / In Hand", "Mark as Returned"): "Returned",
        ("Received / In Hand", "Cancel"): "Cancelled",
        ("Deposited / Under Collection", "Mark as Cleared"): "Cleared",
        ("Deposited / Under Collection", "Mark as Returned"): "Returned",
        # Allow cancellation while cheque is still under collection
        ("Deposited / Under Collection", "Cancel"): "Cancelled",
        ("Returned", "Cancel"): "Cancelled",
    },
    "Outgoing": {
        ("Issued", "Mark as Cleared"): "Cleared",
        ("Issued", "Cancel"): "Cancelled",
        # kept for backward compatibility with any existing outgoing records
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
    "Cancel",
}

SUPPLIER_REQUIRED_MOVEMENT_TYPES = {"Endorse to Supplier"}

# Movement types where a settlement exchange rate is entered by the user
# and an exchange gain / loss is calculated against the original base amount.
EXCHANGE_DIFFERENCE_MOVEMENT_TYPES = {
    "Mark as Cleared",
    "Endorse to Supplier",
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
