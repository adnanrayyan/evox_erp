frappe.query_reports["Cheques Under Collection"] = {
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
			fieldname: "bank_name",
			label: __("Bank Name"),
			fieldtype: "Data",
		},
		{
			fieldname: "due_date_from",
			label: __("Due Date From"),
			fieldtype: "Date",
		},
		{
			fieldname: "due_date_to",
			label: __("Due Date To"),
			fieldtype: "Date",
		},
	],
};

