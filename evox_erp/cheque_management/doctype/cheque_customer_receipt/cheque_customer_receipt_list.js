frappe.listview_settings["Cheque Customer Receipt"] = {
	add_fields: ["customer", "posting_date", "payment_mode", "total_received_amount", "status"],
	get_indicator(doc) {
		const map = {
			Draft: "orange",
			Submitted: "green",
			Cancelled: "red",
		};
		return [__(doc.status), map[doc.status] || "grey", "status,=," + doc.status];
	},
};
