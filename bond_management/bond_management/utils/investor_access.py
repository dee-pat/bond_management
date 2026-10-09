"""Shared permission checks for read-only investor projections."""

import frappe
from frappe import _


def require_readable_portfolio(portfolio: str) -> None:
    readable = frappe.qb.get_query(
        "Bond Portfolio",
        fields=["name"],
        filters={"name": portfolio},
        limit=1,
        ignore_permissions=False,
    ).run(pluck=True)
    if not readable:
        frappe.throw(_("You are not permitted to read this portfolio."), frappe.PermissionError)
