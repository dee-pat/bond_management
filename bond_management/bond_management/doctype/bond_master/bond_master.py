# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.data import getdate
from bond_management.bond_management.utils.coupon_schedule import generate_coupon_schedule

class BondMaster(Document):
	def validate(self):	
		if getdate(self.maturity_date) <= getdate(self.issue_date):
			frappe.throw("Maturity Date must be after Issue Date")
		self.update_maturity_date()
		self.regenerate_coupon_schedule()
		self.validate_principal_alignment()
		self.validate_principal_schedule()
		self.update_principal_percentages()


	def validate_principal_schedule(self):
		total_units = sum(r.principal_units for r in self.principal_schedule)
		if total_units <= 0:
			frappe.throw("Total principal units must be greater than zero")

	def update_principal_percentages(self):
		total_units = sum(r.principal_units for r in self.principal_schedule)

		if not total_units:
			return

		for row in self.principal_schedule:
			row.repayment_percent = (row.principal_units / total_units) * 100

	def update_maturity_date(self):
		dates = [
			getdate(row.repayment_date)
			for row in self.principal_schedule
			if row.repayment_date
		]

		if not dates:
			self.maturity_date = None
			return

		self.maturity_date = max(dates)


	def regenerate_coupon_schedule(self):
		if not self.issue_date or not self.maturity_date or not self.coupon_frequency:
			return

		schedule = generate_coupon_schedule(
			self.issue_date,
			self.maturity_date,
			self.coupon_frequency
		)

		self.set("coupon_schedule", [])

		for row in schedule:
			self.append("coupon_schedule", row)

	def validate_principal_alignment(self):
		if not self.coupon_schedule or not self.principal_schedule:
			return

		coupon_dates = {
			getdate(row.coupon_date)
			for row in self.coupon_schedule
			if row.coupon_date
		}

		for row in self.principal_schedule:
			if not row.repayment_date:
				continue

			repayment_date = getdate(row.repayment_date)

			if repayment_date not in coupon_dates:
				frappe.throw(
					f"Repayment date {repayment_date} must match a coupon date"
				)