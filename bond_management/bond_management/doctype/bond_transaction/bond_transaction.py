# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.accrual import get_accrued_interest
from bond_management.bond_management.utils.portfolio import get_position


class BondTransaction(Document):
    def validate(self):
        self.calculate_amounts()

        if getdate(self.settlement_date) > getdate(self.maturity_date):
            frappe.throw("Settlement Date must be on or before Maturity Date")
        if getdate(self.settlement_date) < getdate(self.issue_date):
            frappe.throw("Settlement Date must be on or after Issue Date")

        position = get_position(
            isin=self.isin,
            statement_date=self.settlement_date,
            portfolio_name=self.portfolio_name,
            exclude_name=self.name,
        )

        if self.transaction_type == "Sale" and self.quantity_face_value > position:
            frappe.throw("Cannot sell more than current position")

    @frappe.whitelist()
    def calculate_amounts(self):
        self.principal = (self.face_value_per_unit or 0) * (
            self.quantity_face_value or 0
        )
        self.commission_amount = (
            (self.principal or 0) * float(self.commission or 0) / 100
        )
        self.settlement_amount = (
            self.principal * (self.price or 0) / 100 + (self.accrued_interest_paid or 0)
        )
        if self.isin and self.settlement_date and self.quantity_face_value:
            self.accrued_interest_calculated = get_accrued_interest(
                isin=self.isin,
                settlement_date=self.settlement_date,
                quantity_face_value=self.quantity_face_value,
            )

        return {
            "principal": self.principal,
            "commission_amount": self.commission_amount,
            "settlement_amount": self.settlement_amount,
            "accrued_interest_calculated": self.accrued_interest_calculated,
        }
