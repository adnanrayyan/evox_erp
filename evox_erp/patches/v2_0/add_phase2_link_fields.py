"""
Phase 2 link fields patch.

Frappe migrate handles all schema changes (new columns) automatically via
DocType JSON. This patch sets sensible defaults on existing Cheque Register
and Cheque Movement records so they behave correctly after the upgrade.

Specifically:
- current_movement on each Cheque Register is set to its latest submitted movement.
- accounting_posted on Cheque Movement remains 0 for pre-Phase-2 records
  (they have no journal_entry, so 0 is correct).
"""

import frappe


def execute():
    _backfill_current_movement()


def _backfill_current_movement():
    """
    For every submitted Cheque Register that has submitted movements,
    set current_movement to the most recent submitted movement.
    This is idempotent — safe to run multiple times.
    """
    cheques_with_movements = frappe.db.sql("""
        SELECT DISTINCT cheque
        FROM `tabCheque Movement`
        WHERE docstatus = 1
    """, as_list=True)

    for (cheque_name,) in cheques_with_movements:
        latest = frappe.db.sql("""
            SELECT name
            FROM `tabCheque Movement`
            WHERE cheque = %s AND docstatus = 1
            ORDER BY creation DESC, name DESC
            LIMIT 1
        """, (cheque_name,), as_list=True)

        if latest:
            frappe.db.set_value(
                "Cheque Register",
                cheque_name,
                "current_movement",
                latest[0][0],
                update_modified=False,
            )

    frappe.db.commit()
