import frappe

from bond_management.bond_management.utils.accrual import calculate_weighted_average_repayment


def execute():
    """Backfill weighted repayment values on existing market-price rows."""
    market_date = frappe.qb.DocType("Bond Market Date")
    market_price = frappe.qb.DocType("Bond Market Prices")
    rows = (
        frappe.qb.from_(market_price)
        .inner_join(market_date)
        .on(market_price.parent == market_date.name)
        .select(market_price.name, market_price.isin, market_date.date)
        .where(
            (market_price.parenttype == "Bond Market Date")
            & (market_price.parentfield == "bond_market_prices")
        )
    ).run(as_dict=True)

    principal_schedules = {}
    for row in rows:
        if not row.isin:
            continue

        if row.isin not in principal_schedules:
            bond = frappe.get_doc("Bond Master", row.isin)
            principal_schedules[row.isin] = bond.get("principal_schedule")

        weighted_date, weighted_years = calculate_weighted_average_repayment(
            principal_schedules[row.isin], row.date
        )
        frappe.db.set_value(
            "Bond Market Prices",
            row.name,
            {
                "weighted_avg_repayment_date": weighted_date,
                # Frappe numeric columns are non-nullable; zero is also excluded
                # by the chart's positive-years filter when no repayment remains.
                "weighted_avg_repayment_years": weighted_years or 0,
            },
            update_modified=False,
        )
