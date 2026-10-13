# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from datetime import date as Date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from bond_management.bond_management.utils.financial import DecimalInput, to_decimal
from bond_management.bond_management.utils.market_data import calculate_market_data
from bond_management.bond_management.utils.validation import optional_string, required_string
from bond_management.bond_management.utils.xirr import (
    DEFAULT_XIRR_GUESS,
    create_future_cash_flows,
    get_last_xirr_guesses,
)


class BondMarketDate(Document):
    def validate(self):
        self._validate_unique_date()
        self._validate_market_price_rows()
        self._recalculate_market_data()

    def _validate_unique_date(self):
        """Allow one market-data snapshot for each valuation date.

        Frappe v16 does not permit a database ``unique`` constraint on Date
        fields, so this business rule is enforced at the document boundary.
        """
        if not self.date:
            return

        filters = {"date": self.date}
        if not self.is_new():
            filters["name"] = ["!=", self.name]

        existing = frappe.qb.get_query(
            "Bond Market Date",
            fields=["name"],
            filters=filters,
            limit=1,
            # A document validation must see an existing duplicate even when
            # the submitting user has restricted read permissions.
            ignore_permissions=True,
        ).run(pluck=True)
        if existing:
            frappe.throw(
                _("Bond Market Date already exists for {0}").format(self.date),
                frappe.UniqueValidationError,
            )

    def _recalculate_market_data(self):
        historical_guesses = (
            get_last_xirr_guesses(
                {row.isin for row in self.bond_market_prices if row.isin},
                self.date,
            )
            if self.date
            else {}
        )
        for row in self.bond_market_prices:
            values = calculate_market_data(
                self.date,
                row.isin,
                row.market_price,
                historical_guess=historical_guesses.get(row.isin, DEFAULT_XIRR_GUESS),
            )
            for fieldname, value in values.items():
                row.set(fieldname, value)

    def _validate_market_price_rows(self):
        seen_isins = set()

        for row in self.bond_market_prices:
            if not row.isin:
                frappe.throw(_("ISIN is required in row {0}").format(row.idx))
            _add_unique_isin(row.isin, seen_isins)
            if row.market_price is None:
                frappe.throw(_("Market Price is required in row {0}").format(row.idx))
            if to_decimal(row.market_price, "Market Price") <= 0:
                frappe.throw(_("Market Price must be greater than zero in row {0}").format(row.idx))


def _add_unique_isin(isin, seen_isins):
    if isin in seen_isins:
        frappe.throw(
            _("ISIN {0} appears more than once in Bond Market Prices").format(frappe.bold(escape_html(isin)))
        )
    seen_isins.add(isin)


@frappe.whitelist(methods=["POST"])
def get_recalculated_market_data(date: str | None = None, rows: str | list | None = None) -> list[dict]:
    """Return derived row values without accepting or returning a form document."""
    date = optional_string(date, "Date")
    rows = frappe.parse_json(rows)
    if not isinstance(rows, list):
        frappe.throw(_("Rows must be a list"))

    seen_names = set()
    seen_isins = set()
    validated_rows = []

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            frappe.throw(_("Row {0} must be an object").format(index))

        row_name = required_string(row.get("name"), f"Row {index} name")
        isin = optional_string(row.get("isin"), f"Row {index} ISIN")
        market_price = row.get("market_price")

        if not row_name or row_name in seen_names:
            frappe.throw(_("Row {0} must have a unique name").format(index))
        seen_names.add(row_name)

        if isin:
            _add_unique_isin(isin, seen_isins)
        if market_price is not None and to_decimal(market_price, "Market Price") <= 0:
            frappe.throw(_("Market Price must be greater than zero in row {0}").format(index))
        validated_rows.append((row_name, isin, market_price))

    if not (
        frappe.has_permission("Bond Market Date", "write")
        or frappe.has_permission("Bond Market Date", "create")
    ):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    result = []
    historical_guesses = get_last_xirr_guesses(seen_isins, date)
    for row_name, isin, market_price in validated_rows:
        if isin and not frappe.has_permission("Bond Master", "read", doc=isin):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

        result.append(
            {
                "name": row_name,
                **calculate_market_data(
                    date,
                    isin,
                    market_price,
                    historical_guess=historical_guesses.get(isin, DEFAULT_XIRR_GUESS),
                ),
            }
        )

    return result


@frappe.whitelist(methods=["POST"])
def get_cashflows(date: Date | str | None, isin: str | None, market_price: DecimalInput) -> list[dict]:
    """Return value-only cash flows without syncing a form Document response."""
    date = required_string(date, "Date")
    isin = required_string(isin, "ISIN")
    market_price = to_decimal(market_price, "Market Price")
    if market_price <= 0:
        frappe.throw(_("Market Price must be greater than zero"))

    frappe.has_permission("Bond Master", "read", doc=isin, throw=True)
    return [
        {
            "isin": isin,
            "type": flow["type"],
            "date": str(flow["date"]),
            "amount": flow["amount"],
        }
        for flow in create_future_cash_flows(isin, date, market_price)
    ]
