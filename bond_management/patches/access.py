"""Idempotent role, DocPerm, and report-role bootstrap shared by the access patches.

DocPerm rows are written directly rather than by saving the parent DocType:
saving the parent can validate unrelated legacy field definitions during a
migration, while a direct write stays scoped to the access rule it owns.
"""

import frappe

INVESTOR_ROLE = "Bond Investor Read Only"
MANAGER_ROLE = "Bond Management Manager"


def ensure_role(role: str) -> None:
    if not frappe.db.exists("Role", role):
        # Install/migrate bootstrap: runs at the migration boundary, not a request.
        frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1}).insert(
            ignore_permissions=True
        )


def docperm_name(doctype: str, role: str, permlevel: int = 0) -> str | None:
    return frappe.db.get_value("DocPerm", {"parent": doctype, "role": role, "permlevel": permlevel}, "name")


def upsert_docperm(doctype: str, role: str, values: dict, *, permlevel: int = 0) -> None:
    """Set ``values`` on the role's DocPerm row, creating the row when it is missing."""
    values = {"permlevel": permlevel, **values}
    if permission_name := docperm_name(doctype, role, permlevel):
        frappe.db.set_value("DocPerm", permission_name, values, update_modified=False)
        return

    # Install/migrate bootstrap: runs at the migration boundary, not a request.
    frappe.get_doc(
        {
            "doctype": "DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role,
            **values,
        }
    ).insert(ignore_permissions=True)


def ensure_report_role(report_name: str, role: str) -> None:
    report = frappe.get_doc("Report", report_name)
    if role not in {row.role for row in report.roles}:
        report.append("roles", {"role": role})
        # Install/migrate bootstrap: runs at the migration boundary, not a request.
        report.save(ignore_permissions=True)
