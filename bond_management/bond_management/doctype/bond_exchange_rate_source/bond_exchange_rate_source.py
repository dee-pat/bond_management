import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.statement_exchange_rates import build_source_key


class BondExchangeRateSource(Document):
    """Server-maintained statement provenance for a global exchange-rate row."""

    def before_validate(self):
        self.source_key = build_source_key(self.exchange_rate, self.statement)

    def validate(self):
        if not frappe.flags.get("in_statement_exchange_rate_sync"):
            frappe.throw(_("Exchange-rate provenance is managed from the Bond Statement PDF."))

        exchange_rate = frappe.db.get_value(
            "Bond Exchange Rate",
            self.exchange_rate,
            ["rate_date", "from_currency", "to_currency"],
            as_dict=True,
        )
        if not exchange_rate:
            frappe.throw(_("The linked Bond Exchange Rate does not exist."))
        statement_date = frappe.db.get_value("Bond Statement", self.statement, "statement_date")
        if not statement_date:
            frappe.throw(_("The linked Bond Statement does not exist."))
        if getdate(statement_date) != getdate(exchange_rate.rate_date):
            frappe.throw(_("Statement-derived exchange rates must match the statement date."))

        rate = to_decimal(self.rate, "Rate")
        if rate <= 0:
            frappe.throw(_("Rate must be greater than zero."))
        if self.reverse_rate not in (None, "") and to_decimal(self.reverse_rate, "Reverse Rate") <= 0:
            frappe.throw(_("Reverse Rate must be greater than zero."))

    def on_trash(self):
        if not frappe.flags.get("in_statement_exchange_rate_sync"):
            frappe.throw(_("Exchange-rate provenance is managed from the Bond Statement PDF."))
