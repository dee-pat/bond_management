from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.data import DateTimeLikeObject

from bond_management.bond_management.utils.financial import quantize_money, to_decimal

REPORTING_CURRENCY = "USD"


def build_exchange_rate_context(rows: Iterable[Mapping[str, Any]] | None) -> dict[str, list[dict]]:
    """Group exchange-rate rows by source currency, with ``Decimal`` rates sorted by rate date."""
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
    rate_date: DateTimeLikeObject,
) -> Decimal:
    """Return the latest known source-to-USD rate on or before ``rate_date``."""
    if from_currency == REPORTING_CURRENCY:
        return Decimal(1)

    normalized_date = getdate(rate_date)
    # Rows are sorted by rate_date in build_exchange_rate_context.
    currency_rates = exchange_rates.get(from_currency, [])
    index = bisect_right(currency_rates, normalized_date, key=lambda row: row["rate_date"])
    if index:
        return currency_rates[index - 1]["rate"]

    frappe.throw(
        _(
            "No USD exchange rate is available for {0} on or before {1}. "
            "Add a Bond Exchange Rate row manually, or attach a statement containing this rate."
        ).format(from_currency, normalized_date)
    )


def convert_cashflows(
    cashflows: Iterable[Mapping[str, Any]],
    exchange_rates: dict[str, list[dict]],
    *,
    currency: str,
    rate_date: DateTimeLikeObject | None = None,
) -> list[dict[str, Any]]:
    """Convert cash-flow amounts from ``currency`` to USD, preserving metadata and sign.

    Each flow uses the rate on or before ``rate_date`` or its own date; amounts
    are quantized to money precision.
    """
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
