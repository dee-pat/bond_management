# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from datetime import date as Date

import frappe
from frappe.model.document import Document

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_schedule,
    calculate_weighted_average_repayment,
)
from bond_management.bond_management.utils.financial import DecimalInput, to_decimal
from bond_management.bond_management.utils.xirr import (
    calculate_future_xirr,
    create_future_cash_flows,
)


class BondMarketDate(Document):
    def validate(self):
        self._validate_unique_date()
        self._validate_market_price_rows(require_complete=True)
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
                f"Bond Market Date already exists for {self.date}",
                frappe.UniqueValidationError,
            )

    def _recalculate_market_data(self):
        for row in self.bond_market_prices:
            values = _calculate_market_data(self.date, row.isin, row.market_price)
            for fieldname, value in values.items():
                row.set(fieldname, value)

    def _validate_market_price_rows(self, require_complete):
        seen_isins = set()

        for row in self.bond_market_prices:
            if not row.isin:
                if require_complete:
                    frappe.throw(f"ISIN is required in row {row.idx}")
                continue

            if row.isin in seen_isins:
                frappe.throw(f"ISIN {frappe.bold(row.isin)} appears more than once in Bond Market Prices")
            seen_isins.add(row.isin)

            if row.market_price is None:
                if require_complete:
                    frappe.throw(f"Market Price is required in row {row.idx}")
                continue

            if to_decimal(row.market_price, "Market Price") <= 0:
                row.future_xirr = None
                frappe.throw(f"Market Price must be greater than zero in row {row.idx}")


@frappe.whitelist(methods=["POST"])
def get_recalculated_market_data(
    date: str | None = None, rows: str | list | None = None
) -> list[dict]:
    """Return derived row values without accepting or returning a form document."""
    if not (
        frappe.has_permission("Bond Market Date", "write")
        or frappe.has_permission("Bond Market Date", "create")
    ):
        frappe.throw("Not permitted", frappe.PermissionError)

    rows = frappe.parse_json(rows)
    if not isinstance(rows, list):
        frappe.throw("Rows must be a list")

    seen_names = set()
    seen_isins = set()
    result = []

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            frappe.throw(f"Row {index} must be an object")

        row_name = row.get("name")
        isin = row.get("isin")
        market_price = row.get("market_price")

        if not row_name or row_name in seen_names:
            frappe.throw(f"Row {index} must have a unique name")
        seen_names.add(row_name)

        if isin:
            if isin in seen_isins:
                frappe.throw(f"ISIN {frappe.bold(isin)} appears more than once in Bond Market Prices")
            seen_isins.add(isin)
            if not frappe.has_permission("Bond Master", "read", doc=isin):
                frappe.throw("Not permitted", frappe.PermissionError)

        if market_price is not None and to_decimal(market_price, "Market Price") <= 0:
            frappe.throw(f"Market Price must be greater than zero in row {index}")

        result.append(
            {
                "name": row_name,
                **_calculate_market_data(date, isin, market_price),
            }
        )

    return result


@frappe.whitelist(methods=["POST"])
def get_cashflows(
    date: Date | str | None, isin: str | None, market_price: DecimalInput
) -> list[dict]:
    """Return value-only cash flows without syncing a form Document response."""
    if not date:
        frappe.throw("Date is required")
    if not isin:
        frappe.throw("ISIN is required")
    market_price = to_decimal(market_price, "Market Price")
    if market_price <= 0:
        frappe.throw("Market Price must be greater than zero")

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


def _calculate_market_data(date, isin, market_price):
    values = {
        "currency": None,
        "future_xirr": None,
        "principal_factor": None,
        "weighted_avg_repayment_date": None,
        "weighted_avg_repayment_years": None,
        "maturity_date": None,
    }
    if not isin:
        return values

    bond_doc = frappe.get_doc("Bond Master", isin)
    values["currency"] = bond_doc.get("currency")
    values["maturity_date"] = bond_doc.get("maturity_date")

    if not date:
        return values

    values["principal_factor"] = calculate_principal_factor_from_schedule(
        bond_doc.get("principal_schedule"), date
    )
    weighted_date, weighted_years = calculate_weighted_average_repayment(
        bond_doc.get("principal_schedule"), date
    )
    values["weighted_avg_repayment_date"] = weighted_date
    values["weighted_avg_repayment_years"] = weighted_years
    if market_price is None:
        return values

    future_xirr = calculate_future_xirr(isin, date, market_price)
    values["future_xirr"] = future_xirr * 100 if future_xirr is not None else None
    return values
