import frappe

from bond_management.patches.access import INVESTOR_ROLE, docperm_name


def execute():
    """Allow investors to run reports whose reference DocType is Bond Portfolio."""
    if permission_name := docperm_name("Bond Portfolio", INVESTOR_ROLE):
        frappe.db.set_value("DocPerm", permission_name, "report", 1, update_modified=False)
