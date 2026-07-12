import frappe
from frappe.utils import getdate


def get_position(isin, statement_date, portfolio_name, exclude_name=None):
    rows = frappe.qb.get_query(
        "Bond Transaction",
        filters={
            "isin": isin,
            "portfolio_name": portfolio_name,
            "settlement_date": ["<=", statement_date],
        },
        fields=["name", "transaction_type", "quantity_face_value", "maturity_date"],
        ignore_permissions=False,
    ).run(as_dict=True)

    position = 0
    for row in rows:
        if row["name"] == exclude_name:
            continue
        if row["maturity_date"] and getdate(row["maturity_date"]) <= getdate(statement_date):
            return 0
        if row["transaction_type"] == "Purchase":
            position += row["quantity_face_value"]
        elif row["transaction_type"] == "Sale":
            position -= row["quantity_face_value"]

    return position


def get_portfolio_bonds(portfolio_name):
    return frappe.qb.get_query(
        "Bond Transaction",
        filters={"portfolio_name": portfolio_name},
        distinct=True,
        fields=["isin"],
        ignore_permissions=False,
    ).run(pluck=True)


def fetch_holdings(portfolio_name, statement_date):
    holdings = []
    for isin in get_portfolio_bonds(portfolio_name):
        quantity = get_position(isin, statement_date, portfolio_name)
        if not quantity:
            continue

        bond = frappe.get_doc("Bond Master", isin)
        holdings.append({"isin": bond.name, "quantity": quantity, "currency": bond.currency})

    return holdings
