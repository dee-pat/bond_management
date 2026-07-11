# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.performance import get_market_price
from bond_management.bond_management.utils.xirr import (
    calculate_principal_factor,
    create_past_cash_flows,
    get_position,
)


class BondStatement(Document):
    def validate(self):
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
            market_price = get_market_price(p.get("isin"), statement_date)
            principal_factor = calculate_principal_factor(p.get("isin"), statement_date)

            self.append(
                "bond_statement_details",
                {
                    "isin": p.get("isin"),
                    "quantity": p.get("quantity"),
                    "currency": p.get("currency"),
                    "market_price": market_price,
                    "principal_factor": principal_factor,
                },
            )


@frappe.whitelist()
def fetch_holdings(portfolio_name, date):
    date = getdate(date)

    results = []

    bonds = get_portfolio_bonds(portfolio_name)

    for isin in bonds:
        qty = get_position(
            isin=isin, statement_date=date, portfolio_name=portfolio_name
        )

        if not qty:
            continue

        bond_doc = frappe.get_doc("Bond Master", isin)

        results.append(
            {"isin": bond_doc.name, "quantity": qty, "currency": bond_doc.currency}
        )
    return results


def get_portfolio_bonds(portfolio_name):
    return frappe.qb.get_query(
        "Bond Transaction",
        filters={"portfolio_name": portfolio_name},
        distinct=True,
        fields=["isin"],
    ).run(pluck=True)
