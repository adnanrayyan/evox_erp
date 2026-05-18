frappe.ui.form.on("Cheque Supplier Payment", {
	setup(frm) {
		frm.set_query("currency", () => ({ filters: { enabled: 1 } }));
		frm.set_query("cash_account", () => ({
			filters: { company: frm.doc.company, account_type: ["in", ["Cash", "Bank"]], is_group: 0 },
		}));
		frm.set_query("cheque_register", "cheques", () => ({
			filters: {
				docstatus: 1,
				cheque_type: "Incoming",
				current_status: "Received / In Hand",
				company: frm.doc.company,
			},
		}));
	},

	refresh(frm) {
		apply_payment_mode_visibility(frm);
	},

	company(frm) {
		if (!frm.doc.company) return;
		frappe.db.get_value("Company", frm.doc.company, "default_currency", (r) => {
			if (r && r.default_currency) frm.set_value("currency", r.default_currency);
		});
		frm.set_value("cash_account", "");
		frm.set_value("supplier_account", "");
	},

	supplier(frm) {
		if (frm.doc.company && frm.doc.supplier) {
			frappe.call({
				method: "erpnext.accounts.party.get_party_account",
				args: { party_type: "Supplier", party: frm.doc.supplier, company: frm.doc.company },
				callback(r) {
					if (r.message) frm.set_value("supplier_account", r.message);
				},
			});
		}
	},

	currency(frm) {
		if (!frm.doc.company || !frm.doc.currency) return;
		frappe.db.get_value("Company", frm.doc.company, "default_currency", (r) => {
			if (r && frm.doc.currency === r.default_currency) {
				frm.set_value("exchange_rate", 1);
			}
		});
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

frappe.ui.form.on("Cheque Supplier Payment Cheque", {
	cheque_register(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.cheque_register) return;
		frappe.call({
			method: "evox_erp.cheque_management.doctype.cheque_movement.cheque_movement.get_cheque_details",
			args: { cheque: row.cheque_register },
			callback(r) {
				if (!r.message) return;
				const d = r.message;
				frappe.model.set_value(cdt, cdn, {
					cheque_no: d.cheque_number,
					original_customer: d.party_type === "Customer" ? d.party : "",
					bank: d.bank_name,
					due_date: d.due_date,
					amount: d.amount,
					currency: d.currency,
					exchange_rate: d.exchange_rate,
					base_amount: d.base_amount,
					current_status: d.current_status,
				});
				calculate_totals(frm);
			},
		});
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

function calculate_totals(frm) {
	const mode = frm.doc.payment_mode;
	const has_cash = ["Cash", "Cash + Cheque"].includes(mode);
	const has_cheque = ["Cheque", "Cash + Cheque"].includes(mode);
	const exchange_rate = flt(frm.doc.exchange_rate) || 1;

	const cash_amount = has_cash ? flt(frm.doc.cash_amount) : 0;
	let cheque_amount = 0;
	if (has_cheque) {
		(frm.doc.cheques || []).forEach((row) => { cheque_amount += flt(row.amount); });
	}

	frm.set_value("cheque_amount", cheque_amount);
	frm.set_value("total_paid_amount", cash_amount + cheque_amount);
	frm.set_value("base_cash_amount", cash_amount * exchange_rate);
	frm.set_value("base_cheque_amount", cheque_amount * exchange_rate);
	frm.set_value("base_total_paid_amount", (cash_amount + cheque_amount) * exchange_rate);
}

function flt(val) {
	return parseFloat(val) || 0;
}
