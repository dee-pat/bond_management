import frappe

from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.xirr import DEFAULT_XIRR_GUESS, calculate_future_xirr


def execute():
    """Recalculate legacy yields without using their ambiguous stored zero guesses."""
    rows = frappe.qb.get_query(
        "Bond Market Date",
        fields=[
            "date",
            "bond_market_prices.name as row_name",
            "bond_market_prices.isin as isin",
            "bond_market_prices.market_price as market_price",
            "bond_market_prices.future_xirr as future_xirr",
        ],
        filters={
            "bond_market_prices.name": ["is", "set"],
            "bond_market_prices.future_xirr_available": 0,
        },
        # Registered migration service: refresh all persisted rows across permissions.
        ignore_permissions=True,
    ).run(as_dict=True)
    for row in rows:
        if to_decimal(row.future_xirr) != 0:
            frappe.db.set_value(
                "Bond Market Prices",
                row.row_name,
                "future_xirr_available",
                1,
                update_modified=False,
            )
            continue

        future_xirr = calculate_future_xirr(
            row.isin, row.date, row.market_price, historical_guess=DEFAULT_XIRR_GUESS
        )
        frappe.db.set_value(
            "Bond Market Prices",
            row.row_name,
            {
                "future_xirr": future_xirr * 100 if future_xirr is not None else 0,
                "future_xirr_available": int(future_xirr is not None),
            },
            update_modified=False,
        )
