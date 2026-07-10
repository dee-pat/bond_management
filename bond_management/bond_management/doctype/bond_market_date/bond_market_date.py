# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from pyxirr import xirr
from collections import defaultdict
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
            if not row.isin or not row.market_price:
                continue

            xirr = calculate_future_xirr(row.isin, self.date, row.market_price)

            try:
                row.future_xirr = xirr * 100 if xirr is not None else None
            except Exception:
                row.future_xirr = None

    @frappe.whitelist()
    def update_principal_factor(self):
        for row in self.bond_market_prices:
            if not row.isin:
                continue

            principal_factor = calculate_principal_factor(row.isin, self.date)

            try:
                row.principal_factor = (
                    principal_factor if principal_factor is not None else None
                )
            except Exception:
                row.principal_factor = None

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

    @frappe.whitelist()
    def get_all_cashflows(self):
        valuation_date = getdate(self.date)

        all_rows = []

        for row in self.bond_market_prices:
            isin = row.isin
            market_price = row.market_price
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
            bond_doc = frappe.get_doc("Bond Master", isin)
            maturity_date = bond_doc.get("maturity_date")

            try:
                row.maturity_date = maturity_date
            except Exception:
                row.maturity_date = None
