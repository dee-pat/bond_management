# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from bond_management.bond_management.utils.accrual import calculate_principal_factor
from bond_management.bond_management.utils.performance import get_market_price
from bond_management.bond_management.utils.portfolio import fetch_holdings


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
