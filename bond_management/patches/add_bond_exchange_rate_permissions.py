"""Bootstrap permissions for shared exchange rates."""

from bond_management.patches.access import INVESTOR_ROLE, MANAGER_ROLE, upsert_docperm

DOCTYPENAME = "Bond Exchange Rate"
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
    # Financial documents are never shared (docs/decisions/0012).
    "share": 0,
    "export": 1,
    "import": 1,
    "report": 1,
}


def execute():
    upsert_docperm(DOCTYPENAME, INVESTOR_ROLE, INVESTOR_PERMISSIONS)
    upsert_docperm(DOCTYPENAME, MANAGER_ROLE, MANAGER_PERMISSIONS)
    upsert_docperm(DOCTYPENAME, SYSTEM_MANAGER_ROLE, MANAGER_PERMISSIONS)
    provenance_permissions = {field: 0 for field in MANAGER_PERMISSIONS}
    provenance_permissions["read"] = 1
    upsert_docperm(DOCTYPENAME, MANAGER_ROLE, provenance_permissions, permlevel=1)
    upsert_docperm(DOCTYPENAME, SYSTEM_MANAGER_ROLE, provenance_permissions, permlevel=1)
