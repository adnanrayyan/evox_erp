frappe.ui.form.on("Cheque Customer Receipt", {
	setup(frm) {
		frm.set_query("currency", () => ({ filters: { enabled: 1 } }));
		frm.set_query("cash_account", () => ({
			filters: { company: frm.doc.company, account_type: ["in", ["Cash", "Bank"]], is_group: 0 },
		}));
		frm.set_query("customer_account", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));
	},

	refresh(frm) {
		apply_payment_mode_visibility(frm);
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("View Journal Entries"), () => {
				frappe.set_route("List", "Journal Entry", {
					cheque_no: frm.doc.name,
				});
			});
		}
	},

	company(frm) {
		if (!frm.doc.company) return;
		frappe.db.get_value("Company", frm.doc.company, "default_currency", (r) => {
			if (r && r.default_currency) {
				frm.set_value("currency", r.default_currency);
			}
		});
		frm.set_value("cash_account", "");
		frm.set_value("customer_account", "");
	},

	customer(frm) {
		if (frm.doc.company && frm.doc.customer) {
			frappe.call({
				method: "erpnext.accounts.party.get_party_account",
				args: { party_type: "Customer", party: frm.doc.customer, company: frm.doc.company },
				callback(r) {
					if (r.message) frm.set_value("customer_account", r.message);
				},
			});
		}
	},

	currency(frm) {
		reset_exchange_rate(frm);
	},

	exchange_rate(frm) {
		calculate_totals(frm);
	},

	payment_mode(frm) {
		apply_payment_mode_visibility(frm);
		calculate_totals(frm);
	},

	cash_amount(frm) {
		calculate_totals(frm);
	},
});

frappe.ui.form.on("Cheque Customer Receipt Cheque", {
	amount(frm) {
		calculate_totals(frm);
	},
	currency(frm) {
		const row = frappe.get_doc("Cheque Customer Receipt Cheque", frm.selected_doc && frm.selected_doc.name);
		if (row && row.currency) {
			const company_currency = get_company_currency(frm);
			if (row.currency === company_currency) {
				frappe.model.set_value(row.doctype, row.name, "exchange_rate", 1);
			}
		}
	},
	exchange_rate(frm) {
		calculate_row_base_amount(frm);
		calculate_totals(frm);
	},
	cheques_remove(frm) {
		calculate_totals(frm);
	},
});

function apply_payment_mode_visibility(frm) {
	const mode = frm.doc.payment_mode;
	const has_cash = ["Cash", "Cash + Cheque"].includes(mode);
	const has_cheque = ["Cheque", "Cash + Cheque"].includes(mode);

	frm.toggle_display(["cash_account", "cash_amount", "base_cash_amount"], has_cash);
	frm.toggle_display(["cheques", "cheque_amount", "base_cheque_amount"], has_cheque);

	if (!has_cash) frm.set_value("cash_amount", 0);
}

function reset_exchange_rate(frm) {
	if (!frm.doc.company || !frm.doc.currency) return;
	frappe.db.get_value("Company", frm.doc.company, "default_currency", (r) => {
		if (r && frm.doc.currency === r.default_currency) {
			frm.set_value("exchange_rate", 1);
		}
	});
}

function get_company_currency(frm) {
	return frappe.defaults.get_default("currency") || "";
}

function calculate_row_base_amount(frm) {
	(frm.doc.cheques || []).forEach((row) => {
		const base = flt(row.amount) * (flt(row.exchange_rate) || 1);
		frappe.model.set_value(row.doctype, row.name, "base_amount", base);
	});
}

function calculate_totals(frm) {
	const mode = frm.doc.payment_mode;
	const has_cash = ["Cash", "Cash + Cheque"].includes(mode);
	const has_cheque = ["Cheque", "Cash + Cheque"].includes(mode);
	const exchange_rate = flt(frm.doc.exchange_rate) || 1;

	const cash_amount = has_cash ? flt(frm.doc.cash_amount) : 0;
	let cheque_amount = 0;
	if (has_cheque) {
		(frm.doc.cheques || []).forEach((row) => {
			cheque_amount += flt(row.amount);
		});
	}

	frm.set_value("cheque_amount", cheque_amount);
	frm.set_value("total_received_amount", cash_amount + cheque_amount);
	frm.set_value("base_cash_amount", cash_amount * exchange_rate);
	frm.set_value("base_cheque_amount", cheque_amount * exchange_rate);
	frm.set_value("base_total_received_amount", (cash_amount + cheque_amount) * exchange_rate);
}

function flt(val) {
	return parseFloat(val) || 0;
}
