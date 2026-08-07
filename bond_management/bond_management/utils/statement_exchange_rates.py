import frappe

from bond_management.bond_management.utils.exchange_rate import REPORTING_CURRENCY


def sync_statement_exchange_rates(statement, exchange_rates) -> None:
    """Make the statement-owned exchange-rate rows match its current PDF."""
    desired_rates = {
        (parsed_rate.from_currency, parsed_rate.to_currency): parsed_rate
        for parsed_rate in exchange_rates or ()
        if parsed_rate.to_currency == REPORTING_CURRENCY
    }
    previously_owned = set(
        frappe.qb.get_query(
            "Bond Exchange Rate",
            fields=["name"],
            filters={"statement": statement.name},
            for_update=True,
            # Ownership cleanup must include rows made stale by a prior PDF even
            # if document permissions or portfolio assignments have since changed.
            ignore_permissions=True,
        ).run(pluck=True)
    )
    retained = set()

    for parsed_rate in desired_rates.values():
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
            for_update=True,
            ignore_permissions=True,
        ).run(pluck=True)

        if existing:
            exchange_rate = frappe.get_doc("Bond Exchange Rate", existing[0])
            exchange_rate.rate = parsed_rate.rate
            exchange_rate.statement = statement.name
            exchange_rate.save()
            retained.add(exchange_rate.name)
            continue

        exchange_rate = frappe.get_doc(
            {
                "doctype": "Bond Exchange Rate",
                **filters,
                "rate": parsed_rate.rate,
                "source": "Statement PDF",
                "statement": statement.name,
            }
        ).insert()
        retained.add(exchange_rate.name)

    for exchange_rate_name in sorted(previously_owned - retained):
        frappe.delete_doc("Bond Exchange Rate", exchange_rate_name)


def delete_statement_exchange_rates(statement_name: str) -> None:
    """Delete derived rows before Frappe checks links while deleting a statement."""
    exchange_rate_names = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=["name"],
        filters={"statement": statement_name},
        for_update=True,
        ignore_permissions=True,
    ).run(pluck=True)
    for exchange_rate_name in exchange_rate_names:
        frappe.delete_doc("Bond Exchange Rate", exchange_rate_name)
