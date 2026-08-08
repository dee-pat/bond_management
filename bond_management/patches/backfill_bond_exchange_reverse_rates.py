from decimal import Decimal

import frappe

from bond_management.bond_management.utils.financial import to_decimal


def execute():
    """Backfill the derived reverse rate for existing exchange-rate rows."""
    rows = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=["name", "rate"],
        ignore_permissions=True,
    ).run(as_dict=True)

    for row in rows:
        rate = to_decimal(row.rate, "Rate")
        if rate <= 0:
            continue

        # Reverse Rate is derived from canonical Rate; preserve document timestamps.
        frappe.db.set_value(
            "Bond Exchange Rate",
            row.name,
            "reverse_rate",
            Decimal("1") / rate,
            update_modified=False,
        )
