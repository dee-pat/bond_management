from decimal import Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.exchange_rate import REPORTING_CURRENCY
from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.statement_exchange_rates import SOURCE_DOCTYPE

ONE = Decimal("1")


class BondExchangeRate(Document):
    def before_validate(self):
        if self.rate_date:
            self.rate_date = getdate(self.rate_date)

        self.to_currency = REPORTING_CURRENCY
        self._set_source_projection()
        self._sync_rate_values()

    def validate(self):
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
                ["statement_date"],
                as_dict=True,
            )
            if not statement:
                frappe.throw(_("The linked Bond Statement does not exist"))
            if getdate(statement.statement_date) != self.rate_date:
                frappe.throw(_("Statement-derived exchange rates must match the statement date"))

        filters = {
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
                _("An exchange rate already exists for {0} on {1}").format(
                    self.from_currency, self.rate_date
                ),
                frappe.UniqueValidationError,
            )

    def on_trash(self):
        if frappe.flags.get("in_statement_exchange_rate_sync"):
            return
        if self._statement_sources():
            frappe.throw(
                _(
                    "This exchange-rate row is derived from one or more Bond Statement PDFs. "
                    "Delete or replace the source statement instead."
                )
            )

    def _set_source_projection(self):
        syncing = frappe.flags.get("in_statement_exchange_rate_sync")
        if self.is_new():
            if not syncing:
                self.source = "Manual"
                self.statement = None
                self.manual_fallback = 1
            else:
                self.source = "Statement PDF" if self.statement else "Manual"
            return

        sources = self._statement_sources()
        if sources:
            if not syncing:
                if self._financial_values_changed():
                    frappe.throw(
                        _(
                            "Statement-derived exchange rates are managed from the source PDF. "
                            "Delete or replace the source statement before changing the rate."
                        )
                    )
                self.manual_fallback = self.get_doc_before_save().manual_fallback
            self.source = "Statement PDF"
            self.statement = min(source.statement for source in sources)
            return

        self.source = "Manual"
        self.statement = None
        self.manual_fallback = 1

    def _statement_sources(self):
        # Direct rate edit/delete checks must see derived provenance even when
        # the current user cannot browse the internal source DocType.
        return frappe.get_all(
            SOURCE_DOCTYPE,
            filters={"exchange_rate": self.name},
            fields=["name", "statement"],
            order_by="statement asc, name asc",
            ignore_permissions=True,
        )

    def _financial_values_changed(self):
        previous = self.get_doc_before_save()
        if not previous:
            self.load_doc_before_save()
            previous = self.get_doc_before_save()
        if not previous:
            return True
        return (
            self.from_currency != previous.from_currency
            or self.to_currency != previous.to_currency
            or any(
                _decimal_or_none(self.get(fieldname), fieldname)
                != _decimal_or_none(previous.get(fieldname), fieldname)
                for fieldname in ("rate", "reverse_rate")
            )
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
