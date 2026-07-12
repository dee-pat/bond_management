import frappe


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
        order_by="date desc",
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)

    if result:
        return result[0].market_price or 0.0

    return 0.0
