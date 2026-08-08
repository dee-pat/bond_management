"""Validate legacy exchange-rate scope before dropping the portfolio field."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.database.utils import drop_index_if_exists

from bond_management.patches.add_bond_query_indexes import EXCHANGE_RATE_UNIQUE


def execute():
    """Block ambiguous legacy data, then remove the old scoped unique index."""
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

    drop_index_if_exists("tabBond Exchange Rate", EXCHANGE_RATE_UNIQUE)


def get_exchange_rate_conflicts(rows):
    """Group legacy rows that collide after portfolio scope is removed."""
    rows_by_key = defaultdict(list)
    for row in rows:
        key = (row.rate_date, row.from_currency, row.to_currency)
        rows_by_key[key].append(row)

    return [group for group in rows_by_key.values() if len(group) > 1]


def format_exchange_rate_conflicts(conflicts) -> str:
    """Return actionable migration error without choosing a financial rate."""
    details = []
    for rows in conflicts[:10]:
        key = rows[0]
        values = "; ".join(
            _("{0} ({1}, rate {2})").format(row.name, row.portfolio_name, row.rate) for row in rows
        )
        details.append(
            _("{0} / {1} on {2}: {3}").format(key.from_currency, key.to_currency, key.rate_date, values)
        )

    suffix = "" if len(conflicts) <= 10 else _("; and {0} more conflict(s)").format(len(conflicts) - 10)
    return _(
        "Cannot remove Bond Exchange Rate portfolio scope because duplicate global keys exist: "
        "{0}{1}. Choose one row for each date/currency pair, then remove or correct the other rows and run migrate again."
    ).format(" | ".join(details), suffix)
