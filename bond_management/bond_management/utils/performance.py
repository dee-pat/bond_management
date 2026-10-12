from collections import defaultdict

import frappe
from frappe.utils import getdate

from bond_management.bond_management.utils.exchange_rate import build_exchange_rate_context
from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.investor_permissions import (
    include_shared_exchange_rates_in_safe_projection,
)
from bond_management.bond_management.utils.market_history import latest_market_rows
from bond_management.bond_management.utils.xirr import (
    DEFAULT_XIRR_GUESS,
    get_last_xirr_guesses,
)


def get_latest_market_rows(isins, valuation_date):
    """Return only the latest persisted market row per ISIN."""
    if not isins:
        return []

    return latest_market_rows(
        isins,
        valuation_date,
        ("market_price", "future_xirr", "future_xirr_available"),
    )


def _empty_context(transactions_by_isin):
    return {
        "isins": [],
        "bonds": {},
        "transactions": transactions_by_isin,
        "market_prices": {},
        "xirr_guesses": {},
        "exchange_rates": {},
    }


def load_portfolio_performance_context(portfolio, valuation_date):
    """Batch-load all permission-aware inputs used by statements and reports."""
    valuation_date = getdate(valuation_date)
    transactions = frappe.qb.get_query(
        "Bond Transaction",
        fields=[
            "name",
            "isin",
            "transaction_type",
            "quantity_face_value",
            "settlement_amount",
            "settlement_date",
            "accrued_interest_paid",
        ],
        filters={"portfolio_name": portfolio, "settlement_date": ["<=", valuation_date]},
        order_by="settlement_date asc, name asc",
        ignore_permissions=False,
    ).run(as_dict=True)

    transactions_by_isin = defaultdict(list)
    for transaction in transactions:
        transactions_by_isin[transaction.isin].append(transaction)
    isins = sorted(transactions_by_isin)
    if not isins:
        return _empty_context(transactions_by_isin)

    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=[
            "name",
            "currency",
            "face_value_per_unit",
            "coupon_rate",
            "withholding_tax",
            "coupon_frequency",
            "day_count_convention",
            "maturity_date",
            "quantity_change",
        ],
        filters={"name": ["in", isins]},
        ignore_permissions=False,
    ).run(as_dict=True)
    bonds_by_isin = {bond.name: bond for bond in bonds}
    visible_isins = sorted(bonds_by_isin)
    if not visible_isins:
        return _empty_context(transactions_by_isin)

    for bond in bonds:
        bond["coupon_schedule"] = []
        bond["principal_schedule"] = []

    coupon_rows = frappe.qb.get_query(
        "Bond Coupon Schedule",
        fields=["parent", "coupon_date", "period_start", "period_end", "coupon_factor"],
        filters={
            "parent": ["in", visible_isins],
            "parenttype": "Bond Master",
            "parentfield": "coupon_schedule",
        },
        order_by="coupon_date asc",
        parent_doctype="Bond Master",
        ignore_permissions=False,
    ).run(as_dict=True)
    for row in coupon_rows:
        bonds_by_isin[row.parent]["coupon_schedule"].append(row)

    principal_rows = frappe.qb.get_query(
        "Bond Principal Schedule",
        fields=["parent", "repayment_date", "principal_units", "repayment_percent"],
        filters={
            "parent": ["in", visible_isins],
            "parenttype": "Bond Master",
            "parentfield": "principal_schedule",
        },
        order_by="repayment_date asc",
        parent_doctype="Bond Master",
        ignore_permissions=False,
    ).run(as_dict=True)
    for row in principal_rows:
        bonds_by_isin[row.parent]["principal_schedule"].append(row)

    market_prices = {}
    xirr_guesses = {}
    unavailable_xirr_isins = set()
    for row in get_latest_market_rows(visible_isins, valuation_date):
        market_prices[row.isin] = row.market_price
        if row.future_xirr_available and row.future_xirr is not None:
            # Persisted yields are percentages; solver guesses are decimal rates.
            xirr_guesses[row.isin] = float(to_decimal(row.future_xirr) / to_decimal(100))
        else:
            unavailable_xirr_isins.add(row.isin)

    if unavailable_xirr_isins:
        historical_guesses = get_last_xirr_guesses(unavailable_xirr_isins, valuation_date)
        for isin in unavailable_xirr_isins:
            xirr_guesses[isin] = historical_guesses.get(isin, DEFAULT_XIRR_GUESS)

    native_currencies = sorted(
        {bond.get("currency") for bond in bonds if bond.get("currency") and bond.get("currency") != "USD"}
    )
    exchange_rate_rows = []
    if native_currencies:
        with include_shared_exchange_rates_in_safe_projection():
            exchange_rate_rows = frappe.qb.get_query(
                "Bond Exchange Rate",
                fields=["rate_date", "from_currency", "to_currency", "rate"],
                filters={
                    "rate_date": ["<=", valuation_date],
                    "from_currency": ["in", native_currencies],
                    "to_currency": "USD",
                },
                order_by="rate_date asc, from_currency asc, name asc",
                ignore_permissions=False,
            ).run(as_dict=True)

    return {
        "isins": visible_isins,
        "bonds": bonds_by_isin,
        "transactions": transactions_by_isin,
        "market_prices": market_prices,
        "xirr_guesses": xirr_guesses,
        "exchange_rates": build_exchange_rate_context(exchange_rate_rows),
    }
