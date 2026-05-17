app_name = "evox_erp"
app_title = "EVOX ERP"
app_publisher = "EVOX"
app_description = "Custom ERPNext features for EVOX/OUX"
app_email = "admin@example.com"
app_license = "MIT"

required_apps = ["erpnext"]

fixtures = [
    # Export the Cheque Management workspace so it is installed automatically
    # on new sites and restored on migrate without manual UI setup.
    {"dt": "Workspace", "filters": [["name", "in", ["Cheque Management"]]]},
]

