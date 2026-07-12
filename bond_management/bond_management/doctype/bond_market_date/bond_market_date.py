# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from bond_management.bond_management.utils.xirr import (
    calculate_future_xirr,
    create_future_cash_flows,
)
from bond_management.bond_management.utils.accrual import calculate_principal_factor


class BondMarketDate(Document):

    def validate(self):
        self.update_future_xirr()
        self.update_principal_factor()
        self.update_maturity_date()

    @frappe.whitelist()
    def update_future_xirr(self):
        for row in self.bond_market_prices:
            if not row.isin or row.market_price is None:
                continue

            future_xirr = calculate_future_xirr(row.isin, self.date, row.market_price)
            row.future_xirr = future_xirr * 100 if future_xirr is not None else None

    @frappe.whitelist()
    def update_principal_factor(self):
        for row in self.bond_market_prices:
            if not row.isin:
                continue

            row.principal_factor = calculate_principal_factor(row.isin, self.date)

    @frappe.whitelist()
    def get_cashflows(self, isin, market_price):
        rows = []
        flows = create_future_cash_flows(isin, self.date, market_price)

        for f in flows:
            rows.append(
                {
                    "isin": isin,
                    "type": f["type"],
                    "date": str(f["date"]),
                    "amount": f["amount"],
                }
            )

        return rows

    def get_all_cashflows(self):
        valuation_date = getdate(self.date)

        all_rows = []

        for row in self.bond_market_prices:
            isin = row.isin
            market_price = row.market_price
            if not isin or market_price is None:
                continue
            flows = create_future_cash_flows(isin, valuation_date, market_price)

            for f in flows:
                all_rows.append(
                    {
                        "isin": isin,
                        "type": f.get("type"),
                        "date": getdate(f.get("date")).isoformat(),
                        "amount": float(f.get("amount") or 0.0),
                    }
                )

        return all_rows

    def update_maturity_date(self):
        for row in self.bond_market_prices:
            isin = row.isin
            if not isin:
                continue
            bond_doc = frappe.get_doc("Bond Master", isin)
            row.maturity_date = bond_doc.get("maturity_date")
