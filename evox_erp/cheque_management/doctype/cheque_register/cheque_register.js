frappe.ui.form.on("Cheque Register", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1) {
			return;
		}

		const status = frm.doc.current_status;
		const chequeType = frm.doc.cheque_type;

		if (chequeType === "Incoming" && status === "Received / In Hand") {
			add_action(frm, "Deposit to Bank", "deposit_to_bank", deposit_fields(frm));
			add_action(frm, "Endorse to Supplier", "endorse_to_supplier", supplier_fields());
			add_action(frm, "Return to Customer", "return_to_customer", reason_fields());
			add_action(frm, "Cancel Cheque", "cancel_cheque", reason_fields());
		}

		if (chequeType === "Incoming" && status === "Deposited / Under Collection") {
			add_action(frm, "Mark as Cleared", "mark_as_cleared", posting_fields());
			add_action(frm, "Mark as Returned", "mark_as_returned", reason_fields());
		}

		if (chequeType === "Incoming" && status === "Returned") {
			add_action(frm, "Return to Customer", "return_to_customer", reason_fields());
			add_action(frm, "Cancel Cheque", "cancel_cheque", reason_fields());
		}

		if (chequeType === "Outgoing" && status === "Issued") {
			add_action(frm, "Mark as Cleared", "mark_as_cleared", posting_fields());
			add_action(frm, "Cancel Cheque", "cancel_cheque", reason_fields());
		}
	},
});

function add_action(frm, label, method, fields) {
	frm.add_custom_button(
		__(label),
		() => {
			const call_method = (values = {}) => {
				frappe.call({
					method: `evox_erp.cheque_management.doctype.cheque_register.cheque_register.${method}`,
					args: {
						cheque_name: frm.doc.name,
						...values,
					},
					callback(response) {
						const status = response.message && response.message.status;
						frappe.show_alert({
							message: status
								? __("Cheque status updated to {0}", [status])
								: __("Cheque updated"),
							indicator: "green",
						});
						frm.reload_doc();
					},
				});
			};

			if (fields && fields.length) {
				frappe.prompt(fields, call_method, __(label), __("Submit"));
			} else {
				call_method();
			}
		},
		__("Cheque Actions")
	);
}

function posting_fields() {
	return [
		{
			fieldname: "posting_date",
			fieldtype: "Date",
			label: __("Posting Date"),
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "notes",
			fieldtype: "Small Text",
			label: __("Notes"),
		},
	];
}

function reason_fields() {
	return [
		{
			fieldname: "posting_date",
			fieldtype: "Date",
			label: __("Posting Date"),
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "reason",
			fieldtype: "Small Text",
			label: __("Reason"),
		},
		{
			fieldname: "notes",
			fieldtype: "Small Text",
			label: __("Notes"),
		},
	];
}

function deposit_fields(frm) {
	return [
		{
			fieldname: "bank_account",
			fieldtype: "Link",
			label: __("Bank Account"),
			options: "Account",
			default: frm.doc.deposit_bank_account,
			get_query() {
				return {
					filters: {
						company: frm.doc.company,
					},
				};
			},
		},
		...posting_fields(),
	];
}

function supplier_fields() {
	return [
		{
			fieldname: "supplier",
			fieldtype: "Link",
			label: __("Supplier"),
			options: "Supplier",
			reqd: 1,
		},
		...posting_fields(),
	];
}
