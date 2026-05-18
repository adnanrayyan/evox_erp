frappe.listview_settings["Company Cheque Issue"] = {
	add_fields: ["party_type", "party", "cheque_number", "amount", "due_date", "status"],
	get_indicator(doc) {
		const map = { Draft: "orange", Issued: "blue", Cleared: "green", Cancelled: "red" };
		return [__(doc.status), map[doc.status] || "grey", "status,=," + doc.status];
	},
};
