frappe.ui.form.on("Cheque Register", {
	setup(frm) {
		frm.set_query("currency", () => ({
			filters: {
				enabled: 1,
			},
		}));
	},

	refresh(frm) {
		set_exchange_fields(frm);

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
			add_action(frm, "Mark as Cleared", "mark_as_cleared", clear_fields(frm));
			add_action(frm, "Mark as Returned", "mark_as_returned", bank_reason_fields(frm));
		}

		if (chequeType === "Incoming" && status === "Returned") {
			add_action(frm, "Return to Customer", "return_to_customer", reason_fields());
			add_action(frm, "Cancel Cheque", "cancel_cheque", reason_fields());
		}

		if (chequeType === "Outgoing" && status === "Issued") {
			add_action(frm, "Mark as Cleared", "mark_as_cleared", clear_fields(frm));
			add_action(frm, "Cancel Cheque", "cancel_cheque", reason_fields());
		}
	},

	company(frm) {
		set_company_currency(frm);
	},

	currency(frm) {
		set_exchange_fields(frm);
	},

	amount(frm) {
		calculate_base_amount(frm);
	},

	exchange_rate(frm) {
		calculate_base_amount(frm);
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
			reqd: 1,
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
			reqd: 1,
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

function clear_fields(frm) {
	const fields = deposit_fields(frm);
	const isSameCurrency = frm.doc.currency && frm.doc.company_currency && frm.doc.currency === frm.doc.company_currency;
	if (!isSameCurrency) {
		fields.push({
			fieldname: "movement_exchange_rate",
			fieldtype: "Float",
			label: __("Movement Exchange Rate"),
			default: frm.doc.exchange_rate,
			reqd: 1,
		});
	}
	return fields;
}

function bank_reason_fields(frm) {
	return [
		...deposit_fields(frm),
		{
			fieldname: "reason",
			fieldtype: "Small Text",
			label: __("Reason"),
			reqd: 1,
		},
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

function set_company_currency(frm) {
	if (!frm.doc.company) {
		return;
	}

	frappe.db.get_value("Company", frm.doc.company, "default_currency").then((response) => {
		const currency = response.message && response.message.default_currency;
		if (currency) {
			frm.set_value("company_currency", currency).then(() => set_exchange_fields(frm));
		}
	});
}

function set_exchange_fields(frm) {
	if (!frm.doc.company_currency && frm.doc.company) {
		set_company_currency(frm);
		return;
	}

	const isSameCurrency = frm.doc.currency && frm.doc.company_currency && frm.doc.currency === frm.doc.company_currency;
	frm.toggle_reqd("exchange_rate", Boolean(frm.doc.currency && frm.doc.company_currency && !isSameCurrency));
	frm.set_df_property("exchange_rate", "read_only", isSameCurrency || frm.doc.docstatus === 1);
	if (isSameCurrency && flt(frm.doc.exchange_rate) !== 1) {
		frm.set_value("exchange_rate", 1);
	}
	calculate_base_amount(frm);
}

function calculate_base_amount(frm) {
	const rate = flt(frm.doc.exchange_rate) || 1;
	frm.set_value("base_amount", flt(frm.doc.amount) * rate);
}
