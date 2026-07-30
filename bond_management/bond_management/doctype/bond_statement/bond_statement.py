# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_schedule,
)
from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.performance import load_portfolio_performance_context
from bond_management.bond_management.utils.portfolio import (
    get_ledger_position_from_transactions,
)


class BondStatement(Document):
    def validate(self):
        self.populate_holdings()

    def populate_holdings(self):
        # Clear generated rows first so cleared inputs cannot retain old holdings.
        self.set("bond_statement_details", [])

        if not self.portfolio_name or not self.statement_date:
            return

        context = load_portfolio_performance_context(self.portfolio_name, self.statement_date)
        for isin in context["isins"]:
            bond = context["bonds"][isin]
            quantity = get_ledger_position_from_transactions(
                context["transactions"][isin], self.statement_date
            )
            if getdate(bond.maturity_date) <= getdate(self.statement_date):
                quantity = to_decimal(0)
            if not quantity:
                continue

            market_price = context["market_prices"].get(isin)
            principal_factor = calculate_principal_factor_from_schedule(
                bond.principal_schedule, self.statement_date
            )

            self.append(
                "bond_statement_details",
                {
                    "isin": isin,
                    "quantity": quantity,
                    "currency": bond.currency,
                    "market_price": market_price,
                    "principal_factor": principal_factor,
                },
            )
