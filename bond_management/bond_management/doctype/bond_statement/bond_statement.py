# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from bond_management.bond_management.utils.xirr import calculate_principal_factor


class BondStatement(Document):
    def validate(self):
        pass
        self.populate_holdings()


    def populate_holdings(self):
        if not self.portfolio_name or not self.statement_date:
            return

        positions = fetch_holdings(self.portfolio_name, self.statement_date)

        self.set("bond_statement_details", [])  # clear table

        for p in positions:
            if not p.get("quantity"):
                continue

            statement_date = self.statement_date
            market_price = get_market_price(p.get("isin"), statement_date, self.portfolio_name)
            principal_factor = calculate_principal_factor(p.get("isin"), statement_date)
            
            self.append("bond_statement_details", {	
                "isin": p.get("isin"),
                "quantity": p.get("quantity"),
                "currency": p.get("currency"),
                "market_price": market_price,
                "principal_factor": principal_factor
            })





@frappe.whitelist()
def fetch_holdings(portfolio_name, date):
    from frappe.utils import getdate

    date = getdate(date)

    results = []

    bonds = get_portfolio_bonds(portfolio_name)

    for isin in bonds:
        qty = get_position(isin, date, portfolio_name)

        if not qty:
            continue

        bond_doc = frappe.get_doc("Bond Master", isin)

        results.append({
            "isin": bond_doc.name,
            "quantity": qty,
            "currency": bond_doc.currency
        })
    print("Results:", results)
    return results

def get_portfolio_bonds(portfolio_name):
    return frappe.get_all(
        "Bond Transaction",
        filters={"portfolio_name": portfolio_name},
        pluck="isin",
        distinct=True
    )


def get_position(isin, statement_date, portfolio_name):
    rows = frappe.get_all(
        "Bond Transaction",
        filters={
            "isin": isin,
            "portfolio_name": portfolio_name,
            "settlement_date": ["<=", statement_date],
            #"docstatus": 1
        },
        fields=["transaction_type", "quantity_face_value", "maturity_date"],
    )

    position = 0

    for r in rows:
        if r.maturity_date and getdate(r.maturity_date) <= getdate(statement_date):
            return 0  # Bond has matured, no further transactions affect position
        if r.transaction_type == "Purchase":
            position = position + r.quantity_face_value   
        elif r.transaction_type == "Sale":
             position = position - r.quantity_face_value

    return position


def get_market_price(isin, statement_date, portfolio_name):
    query = frappe.qb.get_query(
        "Bond Market Date",
        filters={
            "date": ["<=", statement_date],
            "bond_market_prices.isin": isin,
            #"docstatus": 1
        },
        fields=["date", "bond_market_prices.market_price"],
        order_by="date desc",
        limit = 1
    )
    
    price_docs = query.run(as_dict=True)
    if price_docs:
        price_doc = price_docs[0] # we want to access the first (and only) document in the list
        return price_doc.get("market_price")
    else:
        return None
