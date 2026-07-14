# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe.utils import flt, getdate

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor,
    unit_accrued_interest,
)
from bond_management.bond_management.utils.performance import (
    get_distinct_isins,
    get_market_price,
)
from bond_management.bond_management.utils.portfolio import get_position
from bond_management.bond_management.utils.xirr import (
    DEFAULT_XIRR_GUESS,
    calculate_xirr,
    consolidate_cashflows,
    create_future_cash_flows,
    create_past_cash_flows,
    get_last_xirr_guess,
    round_cashflow_amount,
)

# ---------- ENTRY POINT ----------


def execute(filters: dict | None = None):
    """Return columns and data for the report.

    This is the main entry point for the report. It accepts the filters as a
    dictionary and should return columns and data. It is called by the framework
    every time the report is refreshed or a filter is updated.
    """
    filters = filters or {}

    portfolio, valuation_date = validate_report_inputs(
        filters.get("portfolio"), filters.get("valuation_date")
    )

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
    portfolio, valuation_date = validate_report_inputs(portfolio, valuation_date)

    if not isin:
        frappe.throw("ISIN is required")
    if xirr_type not in {"past", "future"}:
        frappe.throw("Invalid XIRR type")

    if isin == "TOTAL":
        _, past_cashflows, future_cashflows = get_data(portfolio, valuation_date)
        cashflows = past_cashflows if xirr_type == "past" else future_cashflows
    else:
        portfolio_isins = {
            row["isin"]
            for row in get_distinct_isins(
                portfolio=portfolio, valuation_date=valuation_date
            )
        }
        if isin not in portfolio_isins:
            frappe.throw(
                f"ISIN {frappe.bold(isin)} is not in this portfolio on or before the valuation date"
            )
        if not frappe.has_permission("Bond Master", "read", doc=isin):
            frappe.throw("Not permitted", frappe.PermissionError)

        quantity = get_position(isin, valuation_date, portfolio)
        market_price = get_market_price(isin, valuation_date)
        terminal_market_price = get_terminal_market_price(
            isin, valuation_date, quantity, market_price
        )
        if xirr_type == "past":
            cashflows = create_past_cash_flows(
                isin=isin,
                date=valuation_date,
                market_price=terminal_market_price,
                portfolio=portfolio,
            )
        elif not quantity:
            cashflows = []
        else:
            cashflows = create_future_cash_flows(
                isin, valuation_date, terminal_market_price, quantity=quantity
            )

    return [
        {
            "isin": cashflow["bond"],
            "transaction_type": cashflow["type"],
            "date": getdate(cashflow["date"]).isoformat(),
            "amount": round_cashflow_amount(cashflow["amount"]),
            "quantity": float(cashflow["quantity"]),
            "rate": round_cashflow_amount(cashflow["amount"] / cashflow["quantity"]),
        }
        for cashflow in sorted(
            cashflows,
            key=lambda cashflow: (getdate(cashflow["date"]), float(cashflow["amount"])),
        )
        if float(cashflow["amount"]) != 0
    ]


def validate_report_inputs(portfolio, valuation_date):
    if not portfolio:
        frappe.throw("Portfolio is required")
    if not valuation_date:
        frappe.throw("Valuation Date is required")
    if not frappe.db.exists("Bond Portfolio", portfolio):
        frappe.throw(f"Bond Portfolio {frappe.bold(portfolio)} does not exist")
    if not frappe.has_permission("Bond Portfolio", "read", doc=portfolio):
        frappe.throw("Not permitted", frappe.PermissionError)

    return portfolio, getdate(valuation_date)


def get_terminal_market_price(isin, valuation_date, quantity, market_price):
    """Require a valid quote only when a position still has market exposure."""
    if quantity and market_price is None:
        frappe.throw(
            f"No market price found for {frappe.bold(isin)} on or before {valuation_date}"
        )
    if quantity and flt(market_price) <= 0:
        frappe.throw(f"Market price for {frappe.bold(isin)} must be greater than zero")

    # A closed/matured position needs no artificial terminal valuation. Zero is
    # passed only to the cash-flow builder so it omits that zero-value line.
    return market_price if market_price is not None else 0.0


def calculate_future_xirr_from_cashflows(isin, valuation_date, cashflows):
    """Calculate future XIRR with the same bounded historical guess as the utility."""
    guess = get_last_xirr_guess(isin, valuation_date)
    if guess is None:
        guess = DEFAULT_XIRR_GUESS
    guess = max(min(guess, 1.0), -0.5)
    return calculate_xirr(consolidate_cashflows(cashflows), guess)


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
            "width": 140,
        },
        {"label": "CCY", "fieldname": "currency", "width": 60},
        # {"label": "Face Value/Unit", "fieldname": "face_value_per_unit", "width": 150},
        {
            "label": "Prin. Factor",
            "fieldname": "principal_factor",
            "fieldtype": "Float",
            "width": 110,
        },
        # {"label": "Number of Units", "fieldname": "quantity", "width": 150},
        {
            "label": "Nominal Value",
            "fieldname": "nominal_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        # {"label": "Market Price", "fieldname": "market_price", "fieldtype": "Float", "width": 80,},
        # {"label": "Accrued Interest", "fieldname": "accrued_interest", "fieldtype": "Float", "width": 60,},
        {
            "label": "Purchases Value",
            "fieldname": "purchases_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": "Proceeds Value",
            "fieldname": "proceeds_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
            "description": "Sales, coupon payments and principal amortisation received.",
        },
        {
            "label": "Market Value",
            "fieldname": "market_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": "Gain Value",
            "fieldname": "gain_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {"label": "XIRR", "fieldname": "xirr", "fieldtype": "Percent", "width": 80},
        {
            "label": "Future XIRR",
            "fieldname": "future_xirr",
            "fieldtype": "Percent",
            "width": 105,
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
        terminal_market_price = get_terminal_market_price(
            isin, valuation_date, quantity, market_price
        )
        accrued_interest = unit_accrued_interest(
            isin=isin, settlement_date=valuation_date
        )
        market_value = quantity * (
            face_value_per_unit * terminal_market_price / 100 + accrued_interest
        )

        # ---------- CASHFLOW DATA ----------
        principal_factor = calculate_principal_factor(isin=isin, date=valuation_date)
        nominal_value = quantity * face_value_per_unit * principal_factor

        cashflows = create_past_cash_flows(
            isin=isin,
            date=valuation_date,
            market_price=terminal_market_price,
            portfolio=portfolio,
        )
        combined_cashflow.extend(cashflows)

        totals = defaultdict(float)

        for line in cashflows:
            totals[line.get("type")] += line.get("amount") or 0

        # access:
        purchases_value = -totals["purchase"]
        proceeds_value = totals["sale"] + totals["coupon"] + totals["amortisation"]

        xirr = calculate_xirr(consolidate_cashflows(cashflows))
        xirr = xirr * 100.0 if xirr is not None else 0.0

        if quantity:
            future_cashflows = create_future_cash_flows(
                isin=isin,
                date=valuation_date,
                market_price=terminal_market_price,
                quantity=quantity,
            )
            future_xirr = calculate_future_xirr_from_cashflows(
                isin, valuation_date, future_cashflows
            )
        else:
            future_xirr = None
            future_cashflows = []

        combined_future_cashflow.extend(future_cashflows)

        future_xirr = future_xirr * 100.0 if future_xirr is not None else None

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
                "proceeds_value": proceeds_value,
                "market_value": market_value,
                "gain_value": market_value + proceeds_value - purchases_value,
                "xirr": xirr,
                "future_xirr": future_xirr,
            }
        )

    return rows, combined_cashflow, combined_future_cashflow


# ---------- TOTAL ROW ----------


def make_total_row(data, combined_cashflow, combined_future_cashflow):
    nominal_value = sum(d["nominal_value"] for d in data)
    purchases_value = sum(d["purchases_value"] for d in data)
    proceeds_value = sum(d["proceeds_value"] for d in data)
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
        "proceeds_value": proceeds_value,
        "market_value": market_value,
        "gain_value": gain_value,
        "xirr": xirr_value * 100 if xirr_value is not None else 0.0,
        "future_xirr": future_xirr * 100 if future_xirr is not None else None,
    }
