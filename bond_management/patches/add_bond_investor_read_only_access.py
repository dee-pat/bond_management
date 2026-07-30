import frappe


ROLE = "Bond Investor Read Only"
READ_ONLY_DOCTYPES = (
    "Bond Portfolio",
    "Bond Transaction",
    "Bond Statement",
    "Bond Master",
    "Bond Market Date",
)
PRINTABLE_DOCTYPES = {
    "Bond Transaction",
    "Bond Statement",
    "Bond Master",
    "Bond Market Date",
}


def execute():
    """Create the investor role and grant its non-mutating application access."""
    if not frappe.db.exists("Role", ROLE):
        frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": ROLE,
                "desk_access": 1,
                "is_custom": 1,
            }
        ).insert(ignore_permissions=True)

    for doctype in READ_ONLY_DOCTYPES:
        _ensure_docperm(doctype)

    report = frappe.get_doc("Report", "Portfolio Performance")
    if ROLE not in {row.role for row in report.roles}:
        report.append("roles", {"role": ROLE})
        report.save(ignore_permissions=True)


def _ensure_docperm(doctype: str) -> None:
    """Create or update only the investor DocPerm, without saving its parent DocType.

    Saving the parent can validate unrelated legacy field definitions during a
    migration. Direct DocPerm updates keep this patch idempotent and scoped to
    the access rule it owns.
    """
    permission_name = frappe.db.get_value(
        "DocPerm", {"parent": doctype, "role": ROLE, "permlevel": 0}, "name"
    )
    values = {
        "read": 1,
        "write": 0,
        "create": 0,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "print": int(doctype in PRINTABLE_DOCTYPES),
        "email": 0,
        "share": 0,
        "export": 0,
        "import": 0,
        "report": int(doctype == "Bond Portfolio"),
    }

    if permission_name:
        frappe.db.set_value("DocPerm", permission_name, values, update_modified=False)
        return

    frappe.get_doc(
        {
            "doctype": "DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": ROLE,
            "permlevel": 0,
            **values,
        }
    ).insert(ignore_permissions=True)
