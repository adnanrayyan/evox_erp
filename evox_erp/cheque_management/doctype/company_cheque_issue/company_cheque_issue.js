frappe.ui.form.on("Company Cheque Issue", {
	setup(frm) {
		frm.set_query("currency", () => ({ filters: { enabled: 1 } }));
		frm.set_query("bank_account", () => ({
			filters: { company: frm.doc.company, account_type: "Bank", is_group: 0 },
		}));
		frm.set_query("party_account", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Issued") {
			frm.add_custom_button(__("View Cheque Register"), () => {
				frappe.set_route("Form", "Cheque Register", frm.doc.cheque_register);
			});
		}
	},

	company(frm) {
		if (!frm.doc.company) return;
		frappe.db.get_value("Company", frm.doc.company, "default_currency", (r) => {
			if (r && r.default_currency) frm.set_value("currency", r.default_currency);
		});
		frm.set_value("bank_account", "");
		frm.set_value("party_account", "");
	},

	party_type(frm) {
		frm.set_value("party", "");
		frm.set_value("party_account", "");
	},

	party(frm) {
		if (!frm.doc.company || !frm.doc.party_type || !frm.doc.party) return;
		frappe.call({
			method: "erpnext.accounts.party.get_party_account",
			args: { party_type: frm.doc.party_type, party: frm.doc.party, company: frm.doc.company },
			callback(r) {
				if (r.message) frm.set_value("party_account", r.message);
			},
		});
	},

	currency(frm) {
		if (!frm.doc.company || !frm.doc.currency) return;
		frappe.db.get_value("Company", frm.doc.company, "default_currency", (r) => {
			if (r && frm.doc.currency === r.default_currency) {
				frm.set_value("exchange_rate", 1);
			}
		});
		calculate_base_amount(frm);
	},

	exchange_rate(frm) {
		calculate_base_amount(frm);
	},

	amount(frm) {
		calculate_base_amount(frm);
	},
});

function calculate_base_amount(frm) {
	const exchange_rate = parseFloat(frm.doc.exchange_rate) || 1;
	const amount = parseFloat(frm.doc.amount) || 0;
	frm.set_value("base_amount", amount * exchange_rate);
}
