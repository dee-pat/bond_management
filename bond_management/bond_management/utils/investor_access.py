"""Shared permission checks for read-only investor projections."""

import frappe
from frappe import _


def is_readable(doctype: str, name: str) -> bool:
    """Whether the session user's permission-scoped query can see the named record."""
    return bool(
        frappe.qb.get_query(
            doctype,
            fields=["name"],
            filters={"name": name},
            limit=1,
            ignore_permissions=False,
        ).run(pluck=True)
    )


def require_readable_portfolio(portfolio: str) -> None:
    """Deny unless the session user can read ``portfolio``; unknown and unreadable look alike."""
    if not is_readable("Bond Portfolio", portfolio):
        frappe.throw(_("You are not permitted to read this portfolio."), frappe.PermissionError)
