import frappe
from frappe.query_builder import DocType


def get_distinct_isins(portfolio=None, valuation_date=None):
    bond_transaction = DocType("Bond Transaction")

    query = frappe.qb.from_(bond_transaction).select(bond_transaction.isin).distinct()

    # optional filters
    if portfolio:
        query = query.where(bond_transaction.portfolio_name == portfolio)

    if valuation_date:
        query = query.where(bond_transaction.settlement_date <= valuation_date)

    bonds = query.run(as_dict=True)
    return sorted(bonds, key=lambda x: x["isin"])


def get_market_price(isin, valuation_date):
    BMP = frappe.qb.DocType("Bond Market Prices")
    BMD = frappe.qb.DocType("Bond Market Date")

    query = (
        frappe.qb.from_(BMP)
        .join(BMD)
        .on(BMP.parent == BMD.name)
        .select(BMP.market_price)
        .where((BMP.isin == isin) & (BMD.date <= valuation_date))
        .orderby(BMD.date, order=frappe.qb.desc)
        .limit(1)
    )

    result = query.run(as_dict=True)

    if result:
        return result[0].market_price or 0.0

    return 0.0
