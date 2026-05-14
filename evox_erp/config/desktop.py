from frappe import _


def get_data():
    return [
        {
            "module_name": "Cheque Management",
            "category": "Modules",
            "label": _("Cheque Management"),
            "color": "#0f766e",
            "icon": "octicon octicon-credit-card",
            "type": "module",
            "description": _("Cheque register and cheque movement workflows for EVOX/OUX."),
        }
    ]

