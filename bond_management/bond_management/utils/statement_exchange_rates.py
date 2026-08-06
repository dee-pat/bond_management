import frappe

from bond_management.bond_management.utils.exchange_rate import REPORTING_CURRENCY


def sync_statement_exchange_rates(statement, exchange_rates) -> None:
    """Upsert statement-provided source-to-USD rates without deleting manual fallbacks."""
    for parsed_rate in exchange_rates or ():
        if parsed_rate.to_currency != REPORTING_CURRENCY:
            continue

        filters = {
            "portfolio_name": statement.portfolio_name,
            "rate_date": statement.statement_date,
            "from_currency": parsed_rate.from_currency,
            "to_currency": parsed_rate.to_currency,
        }
        existing = frappe.qb.get_query(
            "Bond Exchange Rate",
            fields=["name"],
            filters=filters,
            limit=1,
            ignore_permissions=True,
        ).run(pluck=True)

        if existing:
            exchange_rate = frappe.get_doc("Bond Exchange Rate", existing[0])
            exchange_rate.rate = parsed_rate.rate
            exchange_rate.statement = statement.name
            exchange_rate.save()
            continue

        frappe.get_doc(
            {
                "doctype": "Bond Exchange Rate",
                **filters,
                "rate": parsed_rate.rate,
                "source": "Statement PDF",
                "statement": statement.name,
            }
        ).insert()
