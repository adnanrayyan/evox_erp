frappe.query_reports["Cheques by Party"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Select",
			options: "\nCustomer\nSupplier",
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Dynamic Link",
			options: "party_type",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nReceived / In Hand\nDeposited / Under Collection\nCleared\nReturned\nReturned to Customer\nEndorsed to Supplier\nIssued\nCancelled\nReversed",
		},
	],
};

