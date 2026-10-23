"""Create the app-scoped manager role and its full Bond Management access."""

import frappe

from bond_management.patches.access import MANAGER_ROLE, ensure_role, upsert_docperm

ROLE = MANAGER_ROLE
BOND_DOCTYPES = (
    "Bond Market Date",
    "Bond Master",
    "Bond Portfolio",
    "Bond Statement",
    "Bond Transaction",
    "Bond Exchange Rate",
)

FULL_PERMISSIONS = {
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 1,
    "submit": 0,
    "cancel": 0,
    "amend": 0,
    "print": 1,
    "email": 1,
    # Financial documents are never shared (docs/decisions/0012).
    "share": 0,
    "export": 1,
    "import": 1,
    "report": 1,
}


def execute():
    """Create or repair the app role without changing standard Frappe roles."""
    ensure_role(ROLE)
    for doctype in BOND_DOCTYPES:
        upsert_docperm(
            doctype,
            ROLE,
            {**FULL_PERMISSIONS, "import": int(bool(frappe.get_meta(doctype).allow_import))},
        )
