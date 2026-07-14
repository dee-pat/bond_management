import frappe


ROLE = "Bond Investor Read Only"


def execute():
    """Allow investors to run reports whose reference DocType is Bond Portfolio."""
    portfolio = frappe.get_doc("DocType", "Bond Portfolio")
    permission = next(
        (permission for permission in portfolio.permissions if permission.role == ROLE), None
    )
    if permission is None:
        return

    if not permission.report:
        permission.report = 1
        portfolio.save(ignore_permissions=True)
