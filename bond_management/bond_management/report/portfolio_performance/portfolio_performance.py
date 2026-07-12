# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate
from collections import defaultdict
from bond_management.bond_management.utils.performance import (
    get_market_price,
    get_distinct_isins,
)
from bond_management.bond_management.utils.accrual import (
    unit_accrued_interest,
    calculate_principal_factor,
)
from bond_management.bond_management.utils.xirr import (
    create_past_cash_flows,
    create_future_cash_flows,
    calculate_xirr,
    consolidate_cashflows,
    calculate_past_xirr,
    calculate_future_xirr,
)
from bond_management.bond_management.utils.portfolio import get_position

# ---------- ENTRY POINT ----------


def execute(filters: dict | None = None):
    """Return columns and data for the report.

    This is the main entry point for the report. It accepts the filters as a
    dictionary and should return columns and data. It is called by the framework
    every time the report is refreshed or a filter is updated.
    """
    filters = filters or {}

    portfolio = filters.get("portfolio")
    valuation_date = filters.get("valuation_date")

    if not portfolio:
        frappe.throw("Portfolio is required")
    if not valuation_date:
        frappe.throw("Valuation Date is required")

    valuation_date = getdate(valuation_date)

    # Permission check
    if not frappe.has_permission("Bond Portfolio", "read", doc=portfolio):
        frappe.throw("Not permitted")

    columns = get_columns()
    data, combined_cashflow, combined_future_cashflow = get_data(
        portfolio, valuation_date
    )

    # Add summary row
    currencies = {row["currency"] for row in data if row.get("currency")}
    if data and len(currencies) <= 1:
        total_row = make_total_row(data, combined_cashflow, combined_future_cashflow)
        data.append(total_row)
    return columns, data


@frappe.whitelist(methods=["POST"])
def get_xirr_cashflows(portfolio, valuation_date, isin, xirr_type):
    """Return the raw cash flows behind a report XIRR value for spreadsheet review."""
    if xirr_type not in {"past", "future"}:
        frappe.throw("Invalid XIRR type")
    if not frappe.has_permission("Bond Portfolio", "read", doc=portfolio):
        frappe.throw("Not permitted")

    valuation_date = getdate(valuation_date)
    if isin == "TOTAL":
        _, past_cashflows, future_cashflows = get_data(portfolio, valuation_date)
        cashflows = past_cashflows if xirr_type == "past" else future_cashflows
    else:
        market_price = get_market_price(isin, valuation_date)
        if xirr_type == "past":
            cashflows = create_past_cash_flows(
                isin=isin,
                date=valuation_date,
                market_price=market_price,
                portfolio=portfolio,
            )
        else:
            quantity = get_position(isin, valuation_date, portfolio)
            cashflows = create_future_cash_flows(isin, valuation_date, market_price)
            cashflows = [
                {**cashflow, "amount": cashflow["amount"] * quantity}
                for cashflow in cashflows
            ]

    return [
        {
            "isin": cashflow["bond"],
            "transaction_type": cashflow["type"],
            "date": getdate(cashflow["date"]).isoformat(),
            "amount": float(cashflow["amount"]),
        }
        for cashflow in sorted(
            cashflows,
            key=lambda cashflow: (getdate(cashflow["date"]), float(cashflow["amount"])),
        )
        if float(cashflow["amount"]) != 0
    ]


# ---------- COLUMNS ----------


def get_columns() -> list[dict]:
    """Return columns for the report.

    One field definition per column, just like a DocType field definition.
    """
    return [
        {
            "label": "ISIN",
            "fieldname": "isin",
            "fieldtype": "Link",
            "options": "Bond Master",
            "width": 130,
        },
        {"label": "Currency", "fieldname": "currency", "width": 50},
        # {"label": "Face Value/Unit", "fieldname": "face_value_per_unit", "width": 150},
        {
            "label": "Princlipal Factor",
            "fieldname": "principal_factor",
            "fieldtype": "Float",
            "width": 60,
        },
        # {"label": "Number of Units", "fieldname": "quantity", "width": 150},
        {
            "label": "Nominal Value",
            "fieldname": "nominal_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        # {"label": "Market Price", "fieldname": "market_price", "fieldtype": "Float", "width": 80,},
        # {"label": "Accrued Interest", "fieldname": "accrued_interest", "fieldtype": "Float", "width": 60,},
        {
            "label": "Purchases Value",
            "fieldname": "purchases_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Sales Value",
            "fieldname": "sales_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Coupons Value",
            "fieldname": "coupons_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Amotisation Value",
            "fieldname": "amortisation_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Market Value",
            "fieldname": "market_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": "Gain Value",
            "fieldname": "gain_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {"label": "XIRR", "fieldname": "xirr", "fieldtype": "Percent", "width": 80},
        {
            "label": "Future XIRR",
            "fieldname": "future_xirr",
            "fieldtype": "Percent",
            "width": 80,
        },
    ]


# ---------- CORE DATA ----------


def get_data(portfolio, valuation_date):
    rows = []

    isins = get_distinct_isins(portfolio=portfolio, valuation_date=valuation_date)

    combined_cashflow = []
    combined_future_cashflow = []

    for bond in isins:
        isin = bond["isin"]

        quantity = get_position(
            isin=isin, statement_date=valuation_date, portfolio_name=portfolio
        )

        # ---------- MASTER DATA ----------
        bonds = frappe.qb.get_query(
            "Bond Master",
            fields=["currency", "face_value_per_unit"],
            filters={"name": isin},
            limit=1,
            ignore_permissions=False,
        ).run(as_dict=True)
        if not bonds:
            continue
        bond = bonds[0]
        currency = bond.get("currency")
        face_value_per_unit = bond.get("face_value_per_unit")

        # ---------- MARKET DATA ----------
        market_price = get_market_price(isin=isin, valuation_date=valuation_date)
        accrued_interest = unit_accrued_interest(
            isin=isin, settlement_date=valuation_date
        )
        market_value = quantity * (
            face_value_per_unit * market_price / 100 + accrued_interest
        )

        # ---------- CASHFLOW DATA ----------
        principal_factor = calculate_principal_factor(isin=isin, date=valuation_date)
        nominal_value = quantity * face_value_per_unit * principal_factor

        cashflows = create_past_cash_flows(
            isin=isin,
            date=valuation_date,
            market_price=market_price,
            portfolio=portfolio,
        )
        combined_cashflow.extend(cashflows)

        totals = defaultdict(float)

        for line in cashflows:
            totals[line.get("type")] += line.get("amount") or 0

        # access:
        coupons_value = totals["coupon"]
        amortisation_value = totals["amortisation"]
        purchases_value = -totals["purchase"]
        sales_value = totals["sale"]

        xirr = calculate_past_xirr(
            isin=isin,
            date=valuation_date,
            market_price=market_price,
            portfolio=portfolio,
        )
        xirr = xirr * 100.0 if xirr else 0.0  # percent and handle None

        future_cashflows = create_future_cash_flows(
            isin=isin,
            date=valuation_date,
            market_price=market_price,
        )
        for row in future_cashflows:
            row["amount"] = row["amount"] * quantity

        combined_future_cashflow.extend(future_cashflows)

        future_xirr = calculate_future_xirr(
            isin=isin, date=valuation_date, market_price=market_price
        )
        future_xirr = (
            future_xirr * 100.0 if future_xirr else 0.0
        )  # percent and handle None

        rows.append(
            {
                "isin": isin,
                "currency": currency,
                # "face_value_per_unit": face_value_per_unit,
                "principal_factor": principal_factor,
                # "quantity": quantity,
                "nominal_value": nominal_value,
                # "market_price": market_price,
                # "accrued_interest": accrued_interest,
                "purchases_value": purchases_value,
                "sales_value": sales_value,
                "coupons_value": coupons_value,
                "amortisation_value": amortisation_value,
                "market_value": market_value,
                "gain_value": (
                    market_value
                    + amortisation_value
                    + coupons_value
                    + sales_value
                    - purchases_value
                ),
                "xirr": xirr,
                "future_xirr": future_xirr,
            }
        )

    return rows, combined_cashflow, combined_future_cashflow


# ---------- TOTAL ROW ----------


def make_total_row(data, combined_cashflow, combined_future_cashflow):
    nominal_value = sum(d["nominal_value"] for d in data)
    purchases_value = sum(d["purchases_value"] for d in data)
    sales_value = sum(d["sales_value"] for d in data)
    coupons_value = sum(d["coupons_value"] for d in data)
    amortisation_value = sum(d["amortisation_value"] for d in data)
    market_value = sum(d["market_value"] for d in data)
    gain_value = sum(d["gain_value"] for d in data)

    cash_flows = consolidate_cashflows(cash_flows=combined_cashflow)
    xirr_value = calculate_xirr(cash_flows)

    combined_future_cashflow = consolidate_cashflows(
        cash_flows=combined_future_cashflow
    )

    future_xirr = calculate_xirr(combined_future_cashflow)

    currencies = {row["currency"] for row in data if row.get("currency")}

    return {
        "isin": "TOTAL",
        "currency": currencies.pop() if len(currencies) == 1 else None,
        "nominal_value": nominal_value,
        "purchases_value": purchases_value,
        "sales_value": sales_value,
        "coupons_value": coupons_value,
        "amortisation_value": amortisation_value,
        "market_value": market_value,
        "gain_value": gain_value,
        "xirr": xirr_value * 100 if xirr_value is not None else 0.0,
        "future_xirr": future_xirr * 100 if future_xirr is not None else 0.0,
    }
