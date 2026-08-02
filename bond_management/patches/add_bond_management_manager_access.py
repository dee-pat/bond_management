"""Create the app-scoped manager role and its full Bond Management access."""

import frappe

ROLE = "Bond Management Manager"
BOND_DOCTYPES = (
    "Bond Market Date",
    "Bond Master",
    "Bond Portfolio",
    "Bond Statement",
    "Bond Transaction",
)

FULL_PERMISSIONS = {
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 1,
    "submit": 1,
    "cancel": 1,
    "amend": 1,
    "print": 1,
    "email": 1,
    "share": 1,
    "export": 1,
    "import": 1,
    "report": 1,
}


def execute():
    """Create or repair the app role without changing standard Frappe roles."""
    if not frappe.db.exists("Role", ROLE):
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": ROLE,
                "desk_access": 1,
                "is_custom": 1,
            }
        ).insert(ignore_permissions=True)

    for doctype in BOND_DOCTYPES:
        permission_name = frappe.db.get_value(
            "DocPerm",
            {"parent": doctype, "role": ROLE, "permlevel": 0},
            "name",
        )
        if permission_name:
            frappe.db.set_value("DocPerm", permission_name, FULL_PERMISSIONS, update_modified=False)
            continue

        frappe.get_doc(
            {
                "doctype": "DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": ROLE,
                "permlevel": 0,
                **FULL_PERMISSIONS,
            }
        ).insert(ignore_permissions=True)
