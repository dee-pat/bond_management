from collections import defaultdict

import frappe
from frappe.utils import getdate


def get_distinct_isins(portfolio=None, valuation_date=None):
    filters = {}
    if portfolio:
        filters["portfolio_name"] = portfolio

    if valuation_date:
        filters["settlement_date"] = ["<=", valuation_date]

    bonds = frappe.qb.get_query(
        "Bond Transaction",
        fields=["isin"],
        filters=filters,
        distinct=True,
        ignore_permissions=False,
    ).run(as_dict=True)
    return sorted(bonds, key=lambda x: x["isin"])


def get_market_price(isin, valuation_date):
    result = frappe.qb.get_query(
        "Bond Market Date",
        fields=["bond_market_prices.market_price"],
        filters={"date": ["<=", valuation_date], "bond_market_prices.isin": isin},
        order_by="date desc, name desc",
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)

    if result:
        return result[0].market_price

    return None


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
        return {
            "isins": [],
            "bonds": {},
            "transactions": transactions_by_isin,
            "market_prices": {},
            "xirr_guesses": {},
        }

    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=[
            "name",
            "currency",
            "face_value_per_unit",
            "coupon_rate",
            "coupon_frequency",
            "day_count_convention",
            "maturity_date",
        ],
        filters={"name": ["in", isins]},
        ignore_permissions=False,
    ).run(as_dict=True)
    bonds_by_isin = {bond.name: bond for bond in bonds}
    visible_isins = sorted(bonds_by_isin)
    if not visible_isins:
        return {
            "isins": [],
            "bonds": {},
            "transactions": transactions_by_isin,
            "market_prices": {},
            "xirr_guesses": {},
        }

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

    market_rows = frappe.qb.get_query(
        "Bond Market Date",
        fields=[
            "date",
            "name",
            "bond_market_prices.isin as isin",
            "bond_market_prices.market_price as market_price",
            "bond_market_prices.future_xirr as future_xirr",
        ],
        filters={
            "date": ["<=", valuation_date],
            "bond_market_prices.isin": ["in", visible_isins],
        },
        order_by="date desc, name desc",
        ignore_permissions=False,
    ).run(as_dict=True)

    market_prices = {}
    xirr_guesses = {}
    for row in market_rows:
        market_prices.setdefault(row.isin, row.market_price)
        if row.future_xirr is not None:
            xirr_guesses.setdefault(row.isin, row.future_xirr)

    return {
        "isins": visible_isins,
        "bonds": bonds_by_isin,
        "transactions": transactions_by_isin,
        "market_prices": market_prices,
        "xirr_guesses": xirr_guesses,
    }
