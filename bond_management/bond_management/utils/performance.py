import frappe
from frappe.utils import getdate
from pyxirr import xirr
from frappe.query_builder import DocType
from datetime import timedelta


def get_distinct_isins(portfolio=None, date=None):
    BTransac = DocType("Bond Transaction")

    query = frappe.qb.from_(BTransac).select(BTransac.isin).distinct()

    # optional filters
    if portfolio:
        query = query.where(BTransac.portfolio_name == portfolio)

    if date:
        query = query.where(BTransac.settlement_date <= date)

    bonds = query.run(as_dict=True)
    return sorted(bonds, key=lambda x: x["isin"])

    # return as simple list
    # return [row["isin"] for row in result]


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
