# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate

from bond_management.bond_management.utils.coupon_schedule import generate_coupon_schedule


class BondMaster(Document):
    def validate(self):
        self._recalculate_schedules()

    def _get_recalculated_values(self):
        return {
            "maturity_date": self.maturity_date,
            "principal_schedule": [
                {
                    "name": row.name,
                    "idx": row.idx,
                    "repayment_date": row.repayment_date,
                    "principal_units": row.principal_units,
                    "repayment_percent": row.repayment_percent,
                }
                for row in self.principal_schedule
            ],
            "coupon_schedule": [
                {
                    "coupon_date": row.coupon_date,
                    "period_start": row.period_start,
                    "period_end": row.period_end,
                    "coupon_factor": row.coupon_factor,
                }
                for row in self.coupon_schedule
            ],
        }

    def _recalculate_schedules(self):
        self.validate_financial_terms()
        self.validate_principal_schedule()
        self.update_maturity_date()
        self.validate_dates()
        self.update_principal_percentages()
        self.regenerate_coupon_schedule()
        self.validate_principal_alignment()

    def validate_financial_terms(self):
        if flt(self.face_value_per_unit) <= 0:
            frappe.throw("Face Value Per Unit must be greater than zero")
        if flt(self.coupon_rate) < 0:
            frappe.throw("Coupon Rate must be zero or greater")

    def validate_dates(self):
        if not self.issue_date or not self.maturity_date:
            return
        if getdate(self.maturity_date) <= getdate(self.issue_date):
            frappe.throw("Maturity Date must be after Issue Date")

    def validate_principal_schedule(self):
        if not self.principal_schedule:
            frappe.throw("At least one principal repayment is required")

        repayment_dates = set()
        for row in self.principal_schedule:
            if flt(row.principal_units) <= 0:
                frappe.throw("Principal Units must be greater than zero in every row")
            if not row.repayment_date:
                frappe.throw("Repayment Date is required in every principal schedule row")

            repayment_date = getdate(row.repayment_date)
            if repayment_date in repayment_dates:
                frappe.throw(f"Repayment date {repayment_date} cannot be duplicated")
            repayment_dates.add(repayment_date)

    def update_principal_percentages(self):
        total_units = sum(flt(row.principal_units) for row in self.principal_schedule)
        for row in self.principal_schedule:
            row.repayment_percent = flt(row.principal_units) / total_units * 100

    def update_maturity_date(self):
        dates = [getdate(row.repayment_date) for row in self.principal_schedule if row.repayment_date]
        self.maturity_date = max(dates) if dates else None

    def regenerate_coupon_schedule(self):
        if not self.issue_date or not self.maturity_date or not self.coupon_frequency:
            return

        schedule = generate_coupon_schedule(
            self.issue_date,
            self.maturity_date,
            self.coupon_frequency,
            self.coupon_rate,
            self.first_coupon_date,
            self.day_count_convention,
        )
        self.set("coupon_schedule", [])
        for row in schedule:
            self.append("coupon_schedule", row)

    def validate_principal_alignment(self):
        if not self.coupon_schedule or not self.principal_schedule:
            return

        coupon_dates = {getdate(row.coupon_date) for row in self.coupon_schedule if row.coupon_date}
        for row in self.principal_schedule:
            if row.repayment_date and getdate(row.repayment_date) not in coupon_dates:
                frappe.throw(f"Repayment date {row.repayment_date} must match a coupon date")


@frappe.whitelist(methods=["POST"])
def get_recalculated_schedules(doc):
    """Return authoritative values without syncing a stale unsaved Document to the form."""
    values = frappe.parse_json(doc)
    if not isinstance(values, dict):
        frappe.throw("Bond Master data must be an object")
    values["doctype"] = "Bond Master"

    existing_name = values.get("name")
    if existing_name and frappe.db.exists("Bond Master", existing_name):
        frappe.has_permission("Bond Master", "write", doc=existing_name, throw=True)
    else:
        frappe.has_permission("Bond Master", "create", throw=True)

    bond = frappe.get_doc(values)
    bond._recalculate_schedules()
    return bond._get_recalculated_values()
