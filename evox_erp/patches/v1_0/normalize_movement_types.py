"""
Patch: normalize legacy movement_type values in Cheque Movement records.

Old values that appeared in the original dropdown are mapped to the canonical
six-value list. Records with unrecognised values are left untouched so no data
is lost; a warning is printed for manual review.

Safe to run multiple times (idempotent): canonical values are skipped.
"""

import frappe

CANONICAL = {
    "Deposit to Bank",
    "Mark as Cleared",
    "Mark as Returned",
    "Endorse to Supplier",
    "Cancel",
}

ALIASES = {
    "Deposit": "Deposit to Bank",
    "Clear": "Mark as Cleared",
    "Collected": "Mark as Cleared",
    "Return": "Mark as Returned",
    "Bounce": "Mark as Returned",
    "Return to Customer": "Mark as Returned",
    "Cancel Cheque": "Cancel",
    "Reverse": "Cancel",
}


def execute():
    rows = frappe.db.get_all(
        "Cheque Movement",
        filters={"movement_type": ["not in", list(CANONICAL)]},
        fields=["name", "movement_type"],
    )

    updated = 0
    skipped = []

    for row in rows:
        canonical = ALIASES.get(row.movement_type)
        if canonical:
            frappe.db.set_value(
                "Cheque Movement",
                row.name,
                "movement_type",
                canonical,
                update_modified=False,
            )
            updated += 1
        else:
            skipped.append(f"{row.name} ({row.movement_type})")

    if updated:
        frappe.db.commit()
        print(f"normalize_movement_types: updated {updated} Cheque Movement record(s).")

    if skipped:
        print(
            "normalize_movement_types: the following records have unrecognised "
            "movement_type values and were NOT changed — review manually:\n"
            + "\n".join(f"  {s}" for s in skipped)
        )
