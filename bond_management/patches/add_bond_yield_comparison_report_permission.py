import frappe

ROLE = "Bond Investor Read Only"
DOCTYPE = "Bond Market Date"
PERMISSIONS = {
    "read": 1,
    "write": 0,
    "create": 0,
    "delete": 0,
    "submit": 0,
    "cancel": 0,
    "amend": 0,
    "print": 1,
    "email": 0,
    "share": 0,
    "export": 0,
    "import": 0,
    "report": 1,
}


def execute():
    """Allow read-only investors to run the stored-yield comparison report."""
    permission_name = frappe.db.get_value(
        "DocPerm", {"parent": DOCTYPE, "role": ROLE, "permlevel": 0}, "name"
    )
    if not permission_name:
        if not frappe.db.exists("Role", ROLE):
            return
        frappe.get_doc(
            {
                "doctype": "DocPerm",
                "parent": DOCTYPE,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": ROLE,
                "permlevel": 0,
                **PERMISSIONS,
            }
        ).insert(ignore_permissions=True)
        return

    frappe.db.set_value("DocPerm", permission_name, "report", 1, update_modified=False)
