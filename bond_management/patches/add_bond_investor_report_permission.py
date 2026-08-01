import frappe

ROLE = "Bond Investor Read Only"


def execute():
    """Allow investors to run reports whose reference DocType is Bond Portfolio."""
    permission_name = frappe.db.get_value(
        "DocPerm", {"parent": "Bond Portfolio", "role": ROLE, "permlevel": 0}, "name"
    )
    if not permission_name:
        return

    frappe.db.set_value("DocPerm", permission_name, "report", 1, update_modified=False)
