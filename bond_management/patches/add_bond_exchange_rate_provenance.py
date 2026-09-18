"""Backfill explicit statement provenance for global exchange-rate rows."""

from decimal import Decimal

import frappe

from bond_management.bond_management.utils.statement_exchange_rates import (
    SOURCE_DOCTYPE,
    build_source_key,
    statement_exchange_rate_sync,
)


def execute():
    if not frappe.db.table_exists("Bond Exchange Rate Source"):
        return

    # This is an idempotent migration over existing canonical rows; it runs
    # from the site migration boundary rather than a user request.
    rows = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=["name", "statement", "rate", "reverse_rate"],
        order_by="name asc",
        ignore_permissions=True,
    ).run(as_dict=True)

    with statement_exchange_rate_sync():
        for row in rows:
            if not row.statement:
                frappe.db.set_value(
                    "Bond Exchange Rate",
                    row.name,
                    "manual_fallback",
                    1,
                    update_modified=False,
                )
                continue

            statement_date = frappe.db.get_value("Bond Statement", row.statement, "statement_date")
            if not statement_date:
                frappe.throw(
                    f"Cannot backfill exchange-rate provenance: Bond Statement {row.statement} is missing."
                )

            source_key = build_source_key(row.name, row.statement)
            values = {
                "doctype": SOURCE_DOCTYPE,
                "source_key": source_key,
                "exchange_rate": row.name,
                "statement": row.statement,
                "rate": row.rate,
                "reverse_rate": row.reverse_rate or Decimal(1) / Decimal(str(row.rate)),
            }
            source_name = frappe.db.get_value(SOURCE_DOCTYPE, {"source_key": source_key}, "name")
            if source_name:
                # Existing provenance may belong to a manual fallback shared
                # with this statement; do not take ownership away on rerun.
                continue
            frappe.get_doc(values).insert(ignore_permissions=True)
            frappe.db.set_value(
                "Bond Exchange Rate",
                row.name,
                "manual_fallback",
                0,
                update_modified=False,
            )
