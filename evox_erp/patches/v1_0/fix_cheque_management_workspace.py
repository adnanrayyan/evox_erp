import json

import frappe


APP = "evox_erp"
MODULE = "Cheque Management"
WORKSPACE = "Cheque Management"
BANKING_SIDEBAR = "Banking"

CHEQUE_DOCTYPES = [
    {
        "label": "Cheque Register",
        "link_to": "Cheque Register",
        "color": "Green",
        "doc_view": "List",
        "icon": "list",
    },
    {
        "label": "Cheque Movement",
        "link_to": "Cheque Movement",
        "color": "Blue",
        "doc_view": "List",
        "icon": "arrow-right-left",
    },
    {
        "label": "Cheque Settings",
        "link_to": "Cheque Settings",
        "color": "Grey",
        "doc_view": "List",
        "icon": "settings",
    },
]


def execute():
    """Make Cheque Management visible in Frappe v16 desk surfaces."""
    links = _existing_cheque_doctypes()

    _ensure_module_def()
    _ensure_workspace(links)
    _ensure_workspace_sidebar(links)
    _ensure_desktop_icon()
    _ensure_banking_sidebar_links(links)

    _clear_desk_cache()
    frappe.db.commit()


def _existing_cheque_doctypes():
    return [link for link in CHEQUE_DOCTYPES if frappe.db.exists("DocType", link["link_to"])]


def _ensure_module_def():
    if frappe.db.exists("Module Def", MODULE):
        frappe.db.set_value(
            "Module Def",
            MODULE,
            {"app_name": APP, "custom": 0},
            update_modified=False,
        )
        return

    module = frappe.new_doc("Module Def")
    module.module_name = MODULE
    module.app_name = APP
    module.custom = 0
    module.insert(ignore_permissions=True)


def _ensure_workspace(links):
    if frappe.db.exists("Workspace", WORKSPACE):
        workspace = frappe.get_doc("Workspace", WORKSPACE)
    else:
        workspace = frappe.new_doc("Workspace")
        workspace.name = WORKSPACE

    _set_if_field(workspace, "label", WORKSPACE)
    _set_if_field(workspace, "title", WORKSPACE)
    _set_if_field(workspace, "module", MODULE)
    _set_if_field(workspace, "app", APP)
    _set_if_field(workspace, "type", "Workspace")
    _set_if_field(workspace, "public", 1)
    _set_if_field(workspace, "is_hidden", 0)
    _set_if_field(workspace, "for_user", "")
    _set_if_field(workspace, "parent_page", "")
    _set_if_field(workspace, "icon", "credit-card")
    _set_if_field(workspace, "indicator_color", "green")
    _set_if_field(workspace, "hide_custom", 0)
    _set_if_field(workspace, "sequence_id", 1.0)
    _set_if_field(workspace, "content", _workspace_content(links))

    workspace.set("roles", [])
    workspace.set("links", [])
    workspace.set("shortcuts", [])

    for link in links:
        workspace.append(
            "links",
            {
                "type": "Link",
                "label": link["label"],
                "link_type": "DocType",
                "link_to": link["link_to"],
                "hidden": 0,
                "onboard": 0,
                "is_query_report": 0,
                "link_count": 0,
            },
        )
        workspace.append(
            "shortcuts",
            {
                "type": "DocType",
                "label": link["label"],
                "link_to": link["link_to"],
                "doc_view": link["doc_view"],
                "stats_filter": "[]",
                "color": link["color"],
                "format": "{}",
            },
        )

    _save(workspace)


def _ensure_workspace_sidebar(links):
    if frappe.db.exists("Workspace Sidebar", WORKSPACE):
        sidebar = frappe.get_doc("Workspace Sidebar", WORKSPACE)
    else:
        sidebar = frappe.new_doc("Workspace Sidebar")
        sidebar.title = WORKSPACE

    _set_if_field(sidebar, "title", WORKSPACE)
    _set_if_field(sidebar, "header_icon", "credit-card")
    _set_if_field(sidebar, "module", MODULE)
    _set_if_field(sidebar, "app", APP)
    _set_if_field(sidebar, "standard", 1)
    _set_if_field(sidebar, "for_user", None)
    sidebar.set("items", [])

    sidebar.append(
        "items",
        {
            "label": "Home",
            "link_type": "Workspace",
            "type": "Link",
            "link_to": WORKSPACE,
            "icon": "home",
            "child": 0,
        },
    )
    for link in links:
        sidebar.append("items", _sidebar_link(link, child=0))

    _save(sidebar)


def _ensure_desktop_icon():
    icon_name = frappe.db.exists("Desktop Icon", WORKSPACE) or frappe.db.exists(
        "Desktop Icon", {"label": WORKSPACE, "icon_type": "Link"}
    )

    if icon_name:
        icon = frappe.get_doc("Desktop Icon", icon_name)
    else:
        icon = frappe.new_doc("Desktop Icon")

    _set_if_field(icon, "label", WORKSPACE)
    _set_if_field(icon, "icon_type", "Link")
    _set_if_field(icon, "link_type", "Workspace Sidebar")
    _set_if_field(icon, "link_to", WORKSPACE)
    _set_if_field(icon, "icon", "credit-card")
    _set_if_field(icon, "standard", 1)
    _set_if_field(icon, "app", APP)
    _set_if_field(icon, "hidden", 0)
    _set_if_field(icon, "restrict_removal", 0)
    _set_if_field(icon, "idx", 0)
    icon.set("roles", [])

    _save(icon)


def _ensure_banking_sidebar_links(links):
    if not frappe.db.exists("Workspace Sidebar", BANKING_SIDEBAR):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", BANKING_SIDEBAR)
    cheque_labels = {WORKSPACE, *[link["label"] for link in links]}
    cheque_targets = {WORKSPACE, *[link["link_to"] for link in links]}

    sidebar.items = [
        item
        for item in sidebar.items
        if item.label not in cheque_labels and item.link_to not in cheque_targets
    ]

    sidebar.append(
        "items",
        {
            "label": WORKSPACE,
            "link_type": "DocType",
            "type": "Section Break",
            "icon": "credit-card",
            "child": 0,
            "indent": 1,
            "keep_closed": 0,
        },
    )
    for link in links:
        sidebar.append("items", _sidebar_link(link, child=1))

    _save(sidebar)


def _workspace_content(links):
    content = [
        {
            "id": "cheque-header",
            "type": "header",
            "data": {"text": '<span class="h4">Cheque Management</span>', "col": 12},
        }
    ]

    for link in links:
        content.append(
            {
                "id": "sc-" + frappe.scrub(link["label"]).replace("_", "-"),
                "type": "shortcut",
                "data": {"shortcut_name": link["label"], "col": 3},
            }
        )

    return json.dumps(content, separators=(",", ":"))


def _sidebar_link(link, child):
    return {
        "label": link["label"],
        "link_type": "DocType",
        "type": "Link",
        "link_to": link["link_to"],
        "icon": link["icon"],
        "child": child,
        "collapsible": 1,
        "indent": 0,
        "keep_closed": 0,
        "show_arrow": 0,
    }


def _set_if_field(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _save(doc):
    doc.flags.ignore_permissions = True
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)


def _clear_desk_cache():
    frappe.clear_cache()
    try:
        from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

        clear_desktop_icons_cache()
    except Exception:
        pass
