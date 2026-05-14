import frappe


def get_cheque_columns():
    return [
        {
            "label": "Cheque",
            "fieldname": "cheque",
            "fieldtype": "Link",
            "options": "Cheque Register",
            "width": 150,
        },
        {
            "label": "Cheque Number",
            "fieldname": "cheque_number",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": "Cheque Type",
            "fieldname": "cheque_type",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": "Party Type",
            "fieldname": "party_type",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": "Party",
            "fieldname": "party",
            "fieldtype": "Dynamic Link",
            "options": "party_type",
            "width": 180,
        },
        {
            "label": "Bank Name",
            "fieldname": "bank_name",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Due Date",
            "fieldname": "due_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": "Currency",
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 90,
        },
        {
            "label": "Current Status",
            "fieldname": "current_status",
            "fieldtype": "Data",
            "width": 190,
        },
    ]


def run_cheque_report(filters=None, statuses=None, order_by=None):
    filters = frappe._dict(filters or {})
    conditions = ["docstatus = 1"]
    values = {}

    if statuses:
        conditions.append("current_status in %(statuses)s")
        values["statuses"] = tuple(statuses)
    elif filters.get("status"):
        conditions.append("current_status = %(status)s")
        values["status"] = filters.status

    if filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters.company

    if filters.get("party_type"):
        conditions.append("party_type = %(party_type)s")
        values["party_type"] = filters.party_type

    if filters.get("party"):
        conditions.append("party = %(party)s")
        values["party"] = filters.party

    if filters.get("bank_name"):
        conditions.append("bank_name like %(bank_name)s")
        values["bank_name"] = f"%{filters.bank_name}%"

    from_date = filters.get("due_date_from") or filters.get("from_date")
    to_date = filters.get("due_date_to") or filters.get("to_date")

    if from_date:
        conditions.append("due_date >= %(from_date)s")
        values["from_date"] = from_date

    if to_date:
        conditions.append("due_date <= %(to_date)s")
        values["to_date"] = to_date

    order_by = order_by or "due_date asc, modified desc"
    data = frappe.db.sql(
        f"""
        select
            name as cheque,
            cheque_number,
            cheque_type,
            party_type,
            party,
            bank_name,
            due_date,
            amount,
            currency,
            current_status
        from `tabCheque Register`
        where {" and ".join(conditions)}
        order by {order_by}
        """,
        values,
        as_dict=True,
    )
    return get_cheque_columns(), data

