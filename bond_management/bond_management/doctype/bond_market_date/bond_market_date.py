# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from pyxirr import xirr
from collections import defaultdict
from frappe.utils import getdate
from bond_management.bond_management.utils.xirr import calculate_future_xirr, calculate_principal_factor2

class BondMarketDate(Document):

    def validate(self):
        self.update_future_xirr()
        self.update_principal_factor()



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

            principal_factor = calculate_principal_factor2(row.isin, self.date)

            try:
                row.principal_factor = principal_factor if principal_factor is not None else None
            except Exception:
                row.principal_factor = None

            
	


	