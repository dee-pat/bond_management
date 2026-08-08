"""Bootstrap permissions for shared exchange rates."""

import frappe

DOCTYPENAME = "Bond Exchange Rate"
INVESTOR_ROLE = "Bond Investor Read Only"
MANAGER_ROLE = "Bond Management Manager"
SYSTEM_MANAGER_ROLE = "System Manager"

INVESTOR_PERMISSIONS = {
    "read": 1,
    "report": 1,
    "print": 1,
    "email": 1,
}
MANAGER_PERMISSIONS = {
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 1,
    "print": 1,
    "email": 1,
    "share": 1,
    "export": 1,
    "import": 1,
    "report": 1,
}


def execute():
    _upsert_permission(INVESTOR_ROLE, INVESTOR_PERMISSIONS)
    _upsert_permission(MANAGER_ROLE, MANAGER_PERMISSIONS)
    _upsert_permission(SYSTEM_MANAGER_ROLE, MANAGER_PERMISSIONS)


def _upsert_permission(role, permissions):
    permission_name = frappe.db.get_value(
        "DocPerm", {"parent": DOCTYPENAME, "role": role, "permlevel": 0}, "name"
    )
    values = {"permlevel": 0, **permissions}
    if permission_name:
        frappe.db.set_value("DocPerm", permission_name, values, update_modified=False)
        return

    frappe.get_doc(
        {
            "doctype": "DocPerm",
            "parent": DOCTYPENAME,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role,
            **values,
        }
    ).insert(ignore_permissions=True)
