import frappe

from bond_management.patches.access import INVESTOR_ROLE, docperm_name
from bond_management.patches.add_bond_investor_read_only_access import ensure_investor_read_only_docperm

DOCTYPE = "Bond Market Date"


def execute():
    """Allow read-only investors to run the stored-yield comparison report."""
    if permission_name := docperm_name(DOCTYPE, INVESTOR_ROLE):
        frappe.db.set_value("DocPerm", permission_name, "report", 1, update_modified=False)
    elif frappe.db.exists("Role", INVESTOR_ROLE):
        ensure_investor_read_only_docperm(DOCTYPE)
