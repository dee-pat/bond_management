import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.exchange_rate import REPORTING_CURRENCY
from bond_management.bond_management.utils.financial import to_decimal


class BondExchangeRate(Document):
    def before_validate(self):
        if self.rate_date:
            self.rate_date = getdate(self.rate_date)

        self.to_currency = REPORTING_CURRENCY
        self.source = "Statement PDF" if self.statement else "Manual"

    def validate(self):
        if not self.portfolio_name:
            frappe.throw(_("Portfolio is required"))
        if not self.rate_date:
            frappe.throw(_("Rate Date is required"))
        if not isinstance(self.from_currency, str) or not self.from_currency:
            frappe.throw(_("From Currency is required"))
        if self.from_currency == REPORTING_CURRENCY:
            frappe.throw(_("A USD exchange-rate row is not required"))
        if self.to_currency != REPORTING_CURRENCY:
            frappe.throw(_("To Currency must be USD"))
        if to_decimal(self.rate, "Rate") <= 0:
            frappe.throw(_("Rate must be greater than zero"))

        if self.statement:
            statement = frappe.db.get_value(
                "Bond Statement",
                self.statement,
                ["portfolio_name", "statement_date"],
                as_dict=True,
            )
            if not statement:
                frappe.throw(_("The linked Bond Statement does not exist"))
            if (
                statement.portfolio_name != self.portfolio_name
                or getdate(statement.statement_date) != self.rate_date
            ):
                frappe.throw(
                    _("Statement-derived exchange rates must match the statement portfolio and date")
                )

        filters = {
            "portfolio_name": self.portfolio_name,
            "rate_date": self.rate_date,
            "from_currency": self.from_currency,
            "to_currency": self.to_currency,
        }
        if not self.is_new():
            filters["name"] = ["!=", self.name]

        existing = frappe.qb.get_query(
            "Bond Exchange Rate",
            fields=["name"],
            filters=filters,
            limit=1,
            ignore_permissions=True,
        ).run(pluck=True)
        if existing:
            frappe.throw(
                _("An exchange rate already exists for {0} on {1} in portfolio {2}").format(
                    self.from_currency, self.rate_date, self.portfolio_name
                ),
                frappe.UniqueValidationError,
            )
