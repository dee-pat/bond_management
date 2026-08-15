import frappe

from bond_management.bond_management.utils.accrual import is_quantity_change_bond
from bond_management.bond_management.utils.market_data import calculate_market_data


def execute(bond_names=None):
    """Refresh derived market-row values for Kenya quantity-change bonds."""
    filters = {"name": ["in", bond_names]} if bond_names is not None else None
    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=["name", "currency", "day_count_convention"],
        filters=filters,
        ignore_permissions=True,
    ).run(as_dict=True)
    quantity_change_names = {bond.name for bond in bonds if is_quantity_change_bond(bond)}

    if not quantity_change_names:
        return

    market_date = frappe.qb.DocType("Bond Market Date")
    market_price = frappe.qb.DocType("Bond Market Prices")
    rows = (
        frappe.qb.from_(market_price)
        .inner_join(market_date)
        .on(market_price.parent == market_date.name)
        .select(
            market_price.name,
            market_price.isin,
            market_price.market_price,
            market_date.date,
        )
        .where(
            (market_price.parenttype == "Bond Market Date")
            & (market_price.parentfield == "bond_market_prices")
        )
    ).run(as_dict=True)

    for row in rows:
        if row.isin not in quantity_change_names:
            continue

        values = calculate_market_data(row.date, row.isin, row.market_price)
        values["weighted_avg_repayment_years"] = values["weighted_avg_repayment_years"] or 0
        frappe.db.set_value(
            "Bond Market Prices",
            row.name,
            values,
            update_modified=False,
        )
