import frappe
from frappe.utils import getdate
from pyxirr import xirr
from frappe.query_builder import DocType
from datetime import timedelta
from pypika import functions as fn, Case



def get_transactions(portfolio, date):
    BTransac = DocType("Bond Transaction")

    # CASE expressions
    purchase_case = (
        Case()
        .when(BTransac.transaction_type == "purchase", BTransac.settlement_amount)
        .else_(0)
    )

    sale_case = (
        Case()
        .when(BTransac.transaction_type == "sale", BTransac.settlement_amount)
        .else_(0)
    )

    quantity_case = (
        Case()
        .when(BTransac.transaction_type == "purchase", BTransac.quantity_face_value)
        .when(BTransac.transaction_type == "sale", -BTransac.quantity_face_value)
        .else_(0)
    )

    query = (
        frappe.qb.from_(BTransac)
        .select(
            BTransac.isin,
            BTransac.currency,
            fn.Sum(purchase_case).as_("purchases_value"),
            fn.Sum(sale_case).as_("sales_value"),
            fn.Sum(quantity_case).as_("quantity"),
        )
        .where(
            (BTransac.portfolio_name == portfolio)
            & (BTransac.settlement_date <= date)
        )
        .groupby(BTransac.isin)
    )

    return query.run(as_dict=True)



def get_distinct_isins(portfolio=None, date=None):
    BTransac = DocType("Bond Transaction")

    query = (
        frappe.qb.from_(BTransac)
        .select(BTransac.isin)
        .distinct()
    )

    # optional filters
    if portfolio:
        query = query.where(BTransac.portfolio_name == portfolio)

    if date:
        query = query.where(BTransac.settlement_date <= date)

    bonds = query.run(as_dict=True)
    return sorted(bonds, key=lambda x: x['isin'])

    # return as simple list
    # return [row["isin"] for row in result]



def get_market_price(isin, valuation_date):
    BMP = frappe.qb.DocType("Bond Market Prices")
    BMD = frappe.qb.DocType("Bond Market Date")

    query = (
        frappe.qb
        .from_(BMP)
        .join(BMD).on(BMP.parent == BMD.name)
        .select(BMP.market_price)
        .where(
            (BMP.isin == isin) &
            (BMD.date <= valuation_date)
        )
        .orderby(BMD.date, order=frappe.qb.desc)
        .limit(1)
    )

    result = query.run(as_dict=True)

    if result:
        return result[0].market_price or 0.0

    return 0.0

