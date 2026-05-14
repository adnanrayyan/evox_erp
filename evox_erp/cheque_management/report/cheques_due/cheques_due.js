frappe.query_reports["Cheques Due"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nReceived / In Hand\nDeposited / Under Collection\nCleared\nReturned\nReturned to Customer\nEndorsed to Supplier\nIssued\nCancelled\nReversed",
		},
	],
};

