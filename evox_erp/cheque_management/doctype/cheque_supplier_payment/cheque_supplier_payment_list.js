frappe.listview_settings["Cheque Supplier Payment"] = {
	add_fields: ["supplier", "posting_date", "payment_mode", "total_paid_amount", "status"],
	get_indicator(doc) {
		const map = { Draft: "orange", Submitted: "green", Cancelled: "red" };
		return [__(doc.status), map[doc.status] || "grey", "status,=," + doc.status];
	},
};
