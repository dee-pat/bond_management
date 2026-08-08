from decimal import Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.exchange_rate import REPORTING_CURRENCY
from bond_management.bond_management.utils.financial import to_decimal

ONE = Decimal("1")


class BondExchangeRate(Document):
    def before_validate(self):
        if self.rate_date:
            self.rate_date = getdate(self.rate_date)

        self.to_currency = REPORTING_CURRENCY
        self.source = "Statement PDF" if self.statement else "Manual"
        self._sync_rate_values()

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
        rate = _decimal_or_none(self.rate, "Rate")
        reverse_rate = _decimal_or_none(self.reverse_rate, "Reverse Rate")
        if rate is None and reverse_rate is None:
            frappe.throw(_("Rate or Reverse Rate is required"))
        if rate is None and reverse_rate <= 0:
            frappe.throw(_("Reverse Rate must be greater than zero"))
        if rate is None or rate <= 0:
            frappe.throw(_("Rate must be greater than zero"))
        if reverse_rate is None or reverse_rate <= 0:
            frappe.throw(_("Reverse Rate must be greater than zero"))

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

    def _sync_rate_values(self):
        rate = _decimal_or_none(self.rate, "Rate")
        reverse_rate = _decimal_or_none(self.reverse_rate, "Reverse Rate")

        if not self.is_new() and not self.get_doc_before_save():
            self.load_doc_before_save()

        if self._should_use_reverse_rate(rate, reverse_rate):
            if reverse_rate is None or reverse_rate <= 0:
                return
            rate = ONE / reverse_rate

        if rate and rate > 0:
            self.rate = rate
            if reverse_rate is None or reverse_rate > 0:
                self.reverse_rate = ONE / rate

    def _should_use_reverse_rate(self, rate, reverse_rate) -> bool:
        if reverse_rate is None:
            return False
        if rate is None:
            return True
        if self.is_new():
            return False
        previous = self.get_doc_before_save()
        return bool(
            previous
            and _decimal_or_none(previous.reverse_rate, "Reverse Rate") != reverse_rate
            and _decimal_or_none(previous.rate, "Rate") == rate
        )


def _decimal_or_none(value, field_label: str):
    if value in (None, ""):
        return None
    return to_decimal(value, field_label)
