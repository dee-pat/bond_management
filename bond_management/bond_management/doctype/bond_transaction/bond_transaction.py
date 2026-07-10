# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from bond_management.bond_management.utils.coupon_schedule import get_coupon_schedule

from bond_management.bond_management.utils.accrual import get_accrued_interest
from bond_management.bond_management.utils.xirr import create_past_cash_flows


class BondTransaction(Document):
    def validate(self):
        self.principal = (self.face_value_per_unit or 0) * (
            self.quantity_face_value or 0
        )
        self.commission_amount = (
            (self.principal or 0) * float(self.commission or 0) / 100
        )
        self.settlement_amount = (self.price or 0) * (self.quantity_face_value or 0) + (
            self.accrued_interest_paid or 0
        )

        if getdate(self.settlement_date) > getdate(self.maturity_date):
            frappe.throw("Settlement Date must be before Maturity Date")
        if getdate(self.settlement_date) < getdate(self.issue_date):
            frappe.throw("Settlement Date must be after Issue Date")

        position = self.get_position(
            isin=self.isin,
            portfolio_name=self.portfolio_name,
            exclude_name=self.name,
        )

        print("Current Position: ", position)

        if self.transaction_type == "Sale":
            if self.quantity_face_value > position:
                frappe.throw("Cannot sell more than current position")

        coupon_schedule = get_coupon_schedule(self.isin)

        self.accrued_interest_calculated = get_accrued_interest(
            isin=self.isin,
            settlement_date=self.settlement_date,
            quantity_face_value=self.quantity_face_value,
        )

    def get_position(self, isin, portfolio_name, exclude_name=None):
        query = frappe.qb.get_query(
            "Bond Transaction",
            filters={
                "isin": isin,
                "portfolio_name": portfolio_name,
                # "docstatus": 1
            },
            fields=[
                "name",
                "transaction_type",
                "quantity_face_value",
            ],
        )

        txs = query.run(as_dict=True)
        print("Transactions: ", txs)
        position = 0

        for tx in txs:
            # exclude current doc if editing
            if tx.name == exclude_name:
                continue

            if tx.transaction_type == "Sale":
                position = position - tx.quantity_face_value
            else:
                position = position + tx.quantity_face_value

        return position
