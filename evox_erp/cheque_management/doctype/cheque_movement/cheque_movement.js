frappe.ui.form.on("Cheque Movement", {
	setup(frm) {
		frm.set_query("cheque", () => ({
			filters: {
				docstatus: 1,
			},
		}));

		frm.set_query("bank_account", () => ({
			filters: {
				company: frm.doc.company,
			},
		}));
	},

	refresh(frm) {
		set_read_only_snapshot_fields(frm);
		apply_movement_type_ui(frm);
		calculate_exchange_values(frm);
	},

	cheque(frm) {
		fetch_cheque_details(frm);
	},

	movement_type(frm) {
		apply_movement_type_ui(frm);
		fetch_cheque_details(frm);
	},

	movement_exchange_rate(frm) {
		calculate_exchange_values(frm);
	},
});

function set_read_only_snapshot_fields(frm) {
	[
		"company",
		"cheque_number",
		"current_status",
		"bank_name",
		"bank_branch",
		"due_date",
		"amount",
		"currency",
		"party_type",
		"party",
		"company_currency",
		"original_exchange_rate",
		"original_base_amount",
		"movement_base_amount",
		"exchange_difference",
		"exchange_difference_type",
	].forEach((fieldname) => frm.set_df_property(fieldname, "read_only", 1));
}

function apply_movement_type_ui(frm) {
	const movementType = frm.doc.movement_type;
	const bankMovements = [
		"Deposit to Bank",
		"Deposit",
		"Mark as Cleared",
		"Clear",
		"Collected",
		"Mark as Returned",
		"Return",
	];
	const reasonMovements = ["Mark as Returned", "Return", "Return to Customer", "Cancel", "Cancel Cheque"];
	const supplierMovement = movementType === "Endorse to Supplier";
	const bankMovement = bankMovements.includes(movementType);
	const reasonMovement = reasonMovements.includes(movementType);
	const exchangeMovement = ["Mark as Cleared", "Clear", "Collected"].includes(movementType);
	const isSameCurrency = frm.doc.currency && frm.doc.company_currency && frm.doc.currency === frm.doc.company_currency;

	frm.toggle_display("bank_account", bankMovement);
	frm.toggle_reqd("bank_account", bankMovement);
	frm.toggle_display("supplier", supplierMovement);
	frm.toggle_reqd("supplier", supplierMovement);
	frm.toggle_display("reason", reasonMovement);
	frm.toggle_reqd("reason", reasonMovement);
	frm.set_df_property("movement_exchange_rate", "read_only", !exchangeMovement || isSameCurrency);
	frm.toggle_reqd("movement_exchange_rate", exchangeMovement && !isSameCurrency);
}

function fetch_cheque_details(frm) {
	if (!frm.doc.cheque) {
		return;
	}

	frappe.call({
		method: "evox_erp.cheque_management.doctype.cheque_movement.cheque_movement.get_cheque_details",
		args: {
			cheque: frm.doc.cheque,
		},
		callback(response) {
			const details = response.message;
			if (!details) {
				return;
			}

			frm.set_value({
				company: details.company,
				cheque_number: details.cheque_number,
				amount: details.amount,
				currency: details.currency,
				company_currency: details.company_currency,
				bank_name: details.bank_name,
				bank_branch: details.bank_branch,
				due_date: details.due_date,
				current_status: details.current_status,
				party_type: details.party_type,
				party: details.party,
				original_exchange_rate: details.exchange_rate,
				original_base_amount: details.base_amount,
				movement_exchange_rate: frm.doc.movement_exchange_rate || details.exchange_rate,
			});

			if (!frm.doc.bank_account && details.deposit_bank_account) {
				frm.set_value("bank_account", details.deposit_bank_account);
			}

			apply_movement_type_ui(frm);
			calculate_exchange_values(frm);
		},
	});
}

function calculate_exchange_values(frm) {
	const amount = flt(frm.doc.amount);
	const originalBase = flt(frm.doc.original_base_amount);
	let rate = flt(frm.doc.movement_exchange_rate) || flt(frm.doc.original_exchange_rate) || 1;
	const isSameCurrency = frm.doc.currency && frm.doc.company_currency && frm.doc.currency === frm.doc.company_currency;
	const exchangeMovement = ["Mark as Cleared", "Clear", "Collected"].includes(frm.doc.movement_type);

	if (isSameCurrency) {
		rate = 1;
		if (flt(frm.doc.movement_exchange_rate) !== 1) {
			frm.set_value("movement_exchange_rate", 1);
		}
	}

	const movementBase = amount * rate;
	let difference = 0;
	if (!isSameCurrency && exchangeMovement) {
		difference = movementBase - originalBase;
	}

	frm.set_value("movement_base_amount", movementBase);
	frm.set_value("exchange_difference", difference);
	frm.set_value("exchange_difference_type", difference > 0 ? "Gain" : difference < 0 ? "Loss" : "None");
}
