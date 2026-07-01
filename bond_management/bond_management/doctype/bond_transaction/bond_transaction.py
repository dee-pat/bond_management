# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from turtle import position

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from bond_management.bond_management.utils.coupon_schedule import generate_coupon_schedule
from bond_management.bond_management.utils.accrual import calculate_accrued_fraction


class BondTransaction(Document):
	def validate(self):
		self.principal = (self.face_value_per_unit or 0) * (self.quantity_face_value or 0)
		self.commission_amount = (self.principal or 0) * float(self.commission or 0) / 100
		self.settlement_amount = (self.price or 0) * (self.quantity_face_value or 0) + (self.accrued_interest_paid or 0)
    	
		if getdate(self.settlement_date) > getdate(self.maturity_date):
			frappe.throw("Settlement Date must be before Maturity Date")
		if getdate(self.settlement_date) < getdate(self.issue_date):
			frappe.throw("Settlement Date must be after Issue Date")

		position = self.get_position(self.isin, self.name)

		print("Current Position: ", position)

		if self.transaction_type == "Sale":
			if self.quantity_face_value > position:
				frappe.throw("Cannot sell more than current position")

		coupon_schedule = generate_coupon_schedule(
			self.issue_date, 
			self.maturity_date, 
			self.coupon_frequency
		)
		accrued_fraction = calculate_accrued_fraction(
			coupon_schedule, 
			self.settlement_date, 
			self.day_count_convention, 
			self.face_value_per_unit, 
			self.coupon_frequency, 
			self.coupon_rate
		)
		self.accrued_interest_calculated = (self.quantity_face_value or 0) * accrued_fraction



	def get_position(self, isin, exclude_name=None):
		filters = {
        "isin": isin,
        #"docstatus": 1
    	}

		txs = frappe.get_all(
			"Bond Transaction",
			filters=filters,
			fields=["name", "transaction_type", "quantity_face_value"]
		)

		position = 0

		print("Transactions: ", txs)

		for tx in txs:
			# exclude current doc if editing
			if tx.name == exclude_name:
				continue

			if tx.transaction_type == "Sale":
				position = position - tx.quantity_face_value
			else:
				position = position + tx.quantity_face_value

		return position

