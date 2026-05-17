// Canonical movement types that require a bank account.
const BANK_MOVEMENTS = new Set(["Deposit to Bank", "Mark as Cleared", "Mark as Returned"]);

// Canonical movement types that require a reason field.
const REASON_MOVEMENTS = new Set(["Mark as Returned", "Cancel"]);

// Movement types where the user enters a settlement exchange rate and
// the system calculates an exchange gain / loss vs the original base amount.
const EXCHANGE_MOVEMENTS = new Set(["Mark as Cleared", "Endorse to Supplier"]);

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
		lock_snapshot_fields(frm);
		apply_movement_type_ui(frm);
		calculate_exchange_values(frm);
	},

	cheque(frm) {
		fetch_cheque_details(frm);
	},

	movement_type(frm) {
		// Re-evaluate visible / required fields for the new movement type.
		apply_movement_type_ui(frm);
		// Always reset the movement exchange rate when the type changes so
		// no stale value from a previous selection bleeds through.
		reset_exchange_on_type_change(frm);
	},

	movement_exchange_rate(frm) {
		calculate_exchange_values(frm);
	},
});

// ---------------------------------------------------------------------------
// Field locking
// ---------------------------------------------------------------------------

function lock_snapshot_fields(frm) {
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
	].forEach((f) => frm.set_df_property(f, "read_only", 1));
}

// ---------------------------------------------------------------------------
// UI rules per movement type
// ---------------------------------------------------------------------------

function apply_movement_type_ui(frm) {
	const mt = frm.doc.movement_type;
	const isSameCurrency = is_same_currency(frm);
	const isExchangeMovement = EXCHANGE_MOVEMENTS.has(mt);
	const isBankMovement = BANK_MOVEMENTS.has(mt);
	const isReasonMovement = REASON_MOVEMENTS.has(mt);
	const isSupplierMovement = mt === "Endorse to Supplier";

	frm.toggle_display("bank_account", isBankMovement);
	frm.toggle_reqd("bank_account", isBankMovement);

	frm.toggle_display("supplier", isSupplierMovement);
	frm.toggle_reqd("supplier", isSupplierMovement);

	frm.toggle_display("reason", isReasonMovement);
	frm.toggle_reqd("reason", isReasonMovement);

	// Exchange rate is editable only for foreign-currency cheques on movement
	// types that have accounting settlement impact (Mark as Cleared, Endorse).
	const rateEditable = isExchangeMovement && !isSameCurrency;
	frm.set_df_property("movement_exchange_rate", "read_only", !rateEditable);
	frm.toggle_reqd("movement_exchange_rate", rateEditable);
}

// ---------------------------------------------------------------------------
// Exchange rate reset on movement type change
// ---------------------------------------------------------------------------

function reset_exchange_on_type_change(frm) {
	// Determine the appropriate default rate for the newly selected type.
	const isSameCurrency = is_same_currency(frm);
	const isExchangeMovement = EXCHANGE_MOVEMENTS.has(frm.doc.movement_type);

	if (isSameCurrency) {
		// Same-currency cheques never have an exchange rate other than 1.
		frm.set_value("movement_exchange_rate", 1);
	} else if (isExchangeMovement) {
		// For exchange-impacting movements with foreign currency, default to
		// the original rate so the user can adjust from a sensible baseline.
		frm.set_value("movement_exchange_rate", flt(frm.doc.original_exchange_rate) || 1);
	} else {
		// Non-exchange movements (Deposit, Cancel, Receive) carry the original
		// rate for reference but it has no accounting impact.
		frm.set_value("movement_exchange_rate", flt(frm.doc.original_exchange_rate) || 1);
	}

	// Always recalculate so exchange_difference resets to 0 for non-exchange types.
	calculate_exchange_values(frm);
}

// ---------------------------------------------------------------------------
// Fetch cheque details from server
// ---------------------------------------------------------------------------

function fetch_cheque_details(frm) {
	if (!frm.doc.cheque) {
		return;
	}

	frappe.call({
		method: "evox_erp.cheque_management.doctype.cheque_movement.cheque_movement.get_cheque_details",
		args: { cheque: frm.doc.cheque },
		callback(response) {
			const d = response.message;
			if (!d) {
				return;
			}

			frm.set_value({
				company: d.company,
				cheque_number: d.cheque_number,
				amount: d.amount,
				currency: d.currency,
				company_currency: d.company_currency,
				bank_name: d.bank_name,
				bank_branch: d.bank_branch,
				due_date: d.due_date,
				current_status: d.current_status,
				party_type: d.party_type,
				party: d.party,
				original_exchange_rate: d.exchange_rate,
				original_base_amount: d.base_amount,
				// Always reset to original rate when a new cheque is selected.
				movement_exchange_rate: d.exchange_rate,
			});

			if (!frm.doc.bank_account && d.deposit_bank_account) {
				frm.set_value("bank_account", d.deposit_bank_account);
			}

			apply_movement_type_ui(frm);
			calculate_exchange_values(frm);
		},
	});
}

// ---------------------------------------------------------------------------
// Exchange value calculation (client-side live update)
// ---------------------------------------------------------------------------

function calculate_exchange_values(frm) {
	const amount = flt(frm.doc.amount);
	const originalBase = flt(frm.doc.original_base_amount);
	const isSameCurrency = is_same_currency(frm);
	const isExchangeMovement = EXCHANGE_MOVEMENTS.has(frm.doc.movement_type);

	const rate = isSameCurrency ? 1 : flt(frm.doc.movement_exchange_rate) || flt(frm.doc.original_exchange_rate) || 1;

	if (isSameCurrency && flt(frm.doc.movement_exchange_rate) !== 1) {
		frm.set_value("movement_exchange_rate", 1);
	}

	const movementBase = amount * rate;
	let difference = 0;
	let differenceType = "None";

	if (!isSameCurrency && isExchangeMovement) {
		difference = movementBase - originalBase;
		if (difference > 0) {
			differenceType = "Gain";
		} else if (difference < 0) {
			differenceType = "Loss";
		}
	}

	frm.set_value("movement_base_amount", movementBase);
	frm.set_value("exchange_difference", difference);
	frm.set_value("exchange_difference_type", differenceType);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function is_same_currency(frm) {
	return (
		frm.doc.currency &&
		frm.doc.company_currency &&
		frm.doc.currency === frm.doc.company_currency
	);
}
