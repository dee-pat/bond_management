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
        doc = frappe.get_doc("DocType", doctype)
        permission = next(
            (permission for permission in doc.permissions if permission.role == ROLE), None
        )
        if permission is None:
            permission = doc.append(
                "permissions",
                {
                    "role": ROLE,
                    "read": 1,
                    "print": int(doctype in PRINTABLE_DOCTYPES),
                },
            )

        if doctype == "Bond Portfolio":
            permission.report = 1
        doc.save(ignore_permissions=True)

    report = frappe.get_doc("Report", "Portfolio Performance")
    if ROLE not in {row.role for row in report.roles}:
        report.append("roles", {"role": ROLE})
        report.save(ignore_permissions=True)
