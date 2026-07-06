import frappe
from frappe.utils import getdate
from pyxirr import xirr
from frappe.query_builder import DocType
from datetime import timedelta

def get_transactions(portfolio, date):
    transactions = frappe.qb.get_query(
        "Bond Transactions",
        fields=[
            "isin",
            "SUM(CASE WHEN transaction_type = 'purchase' THEN settlement_amount ELSE 0 END) AS purchase_settlement",
            "SUM(CASE WHEN transaction_type = 'sales' THEN settlement_amount ELSE 0 END) AS sales_settlement",
        ],
        filters={"bond_portfolio": portfolio, "settlement_date": ["<=", date]},
        group_by="isin",
    ).run(as_dict=True)

    return transactions


def get_positions(portfolio, date):
    positions = frappe.qb.get_query(
        "Bond Transactions",
        fields=[
            "isin",
            "SUM(CASE WHEN transaction_type = 'purchase' THEN -quantity_face_value ELSE quantity_face_value END) AS position",
        ],
        filters={"bond_portfolio": portfolio, "settlement_date": ["<=", date]},
        group_by="isin",
    ).run(as_dict=True)

    return positions




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





def get_bond_transactions(isin, portfolio):
    bond_doc = frappe.get_doc(
        "Bond Master"
                              




