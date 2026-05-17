frappe.listview_settings["Cheque Movement"] = {
	add_fields: ["cheque_number", "party", "party_type"],
	hide_name_column: true,

	onload(listview) {
		listview.page.add_field({
			fieldname: "cheque_number",
			label: __("Cheque No"),
			fieldtype: "Data",
			onchange() {
				if (this.value) {
					listview.filter_area.add([
						["Cheque Movement", "cheque_number", "like", `%${this.value}%`],
					]);
				} else {
					listview.filter_area.remove("cheque_number");
				}
			},
		});
	},
};
