from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import getdate

from bond_management.bond_management.utils.financial import quantize_money, to_decimal

REPORTING_CURRENCY = "USD"


def build_exchange_rate_context(rows) -> dict[str, list[dict]]:
    rates = defaultdict(list)
    for row in rows or []:
        rates[row.get("from_currency")].append(
            {
                "rate_date": getdate(row.get("rate_date")),
                "rate": to_decimal(row.get("rate"), "Exchange Rate"),
            }
        )

    for currency_rates in rates.values():
        currency_rates.sort(key=lambda row: row["rate_date"])

    return dict(rates)


def get_rate_for_date(
    exchange_rates: dict[str, list[dict]],
    from_currency: str,
    rate_date,
) -> Decimal:
    """Return the latest known source-to-USD rate on or before ``rate_date``."""
    if from_currency == REPORTING_CURRENCY:
        return Decimal(1)

    normalized_date = getdate(rate_date)
    applicable_rates = [
        row for row in exchange_rates.get(from_currency, []) if row["rate_date"] <= normalized_date
    ]
    if applicable_rates:
        return applicable_rates[-1]["rate"]

    frappe.throw(
        _(
            "No USD exchange rate is available for {0} on or before {1}. "
            "Add a Bond Exchange Rate row manually, or attach a statement containing this rate."
        ).format(from_currency, normalized_date)
    )


def convert_cashflows(
    cashflows,
    exchange_rates,
    *,
    currency: str,
    rate_date=None,
):
    """Convert cash-flow amounts while preserving their metadata and Decimal precision."""
    converted = []
    for cashflow in cashflows:
        effective_date = rate_date or cashflow.get("date")
        rate = get_rate_for_date(
            exchange_rates,
            currency,
            effective_date,
        )
        converted.append(
            {
                **cashflow,
                "amount": quantize_money(to_decimal(cashflow.get("amount")) * rate),
            }
        )
    return converted
