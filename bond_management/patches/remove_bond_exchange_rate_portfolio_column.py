"""Remove orphaned legacy portfolio column after DocType sync."""

import frappe

from bond_management.patches.prepare_bond_exchange_rate_scope import (
    format_exchange_rate_conflicts,
    get_exchange_rate_conflicts,
)


def execute():
    if not frappe.db.table_exists("Bond Exchange Rate"):
        return
    if not frappe.db.has_column("Bond Exchange Rate", "portfolio_name"):
        return

    rows = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=["name", "portfolio_name", "rate_date", "from_currency", "to_currency", "rate"],
        order_by="rate_date asc, from_currency asc, name asc",
        ignore_permissions=True,
    ).run(as_dict=True)
    conflicts = get_exchange_rate_conflicts(rows)
    if conflicts:
        frappe.throw(format_exchange_rate_conflicts(conflicts), frappe.ValidationError)

    frappe.db.sql_ddl("ALTER TABLE `tabBond Exchange Rate` DROP COLUMN `portfolio_name`")

