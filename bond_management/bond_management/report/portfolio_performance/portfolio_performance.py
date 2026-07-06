# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate
from pyxirr import xirr

from bond_management.bond_management.utils.performance import (
    get_positions,
    get_transactions,
)

# ---------- ENTRY POINT ----------


def execute(filters: dict | None = None):
    """Return columns and data for the report.

    This is the main entry point for the report. It accepts the filters as a
    dictionary and should return columns and data. It is called by the framework
    every time the report is refreshed or a filter is updated.
    """
    filters = filters or {}

    portfolio = filters.get("portfolio")
    valuation_date = getdate(filters.get("valuation_date"))

    if not portfolio:
        frappe.throw("Portfolio is required")

    # Permission check
    if not frappe.has_permission("Portfolio", "read", doc=portfolio):
        frappe.throw("Not permitted")

    columns = get_columns()

    data, portfolio_xirr = get_data(portfolio, valuation_date)
    """
    # Add summary row
    if data:
        total_row = make_total_row(data, portfolio_xirr)
        data.append({})
        data.append(total_row)
    return columns, data
    """


# ---------- COLUMNS ----------


def get_columns() -> list[dict]:
    """Return columns for the report.

    One field definition per column, just like a DocType field definition.
    """
    return [
        {"label": "ISIN", "fieldname": "isin", "width": 150},
        {"label": "Currency", "currency": "currency", "width": 50},
        {
            "label": "Face Value/Unit",
            "face_value_per_unit": "face_value_per_unit",
            "width": 50,
        },
        {
            "label": "Princlipal Factor",
            "principal_factor": "principal_factor",
            "width": 50,
        },
        {
            "label": "Factored Nonimal Value",
            "nominal_value": "nominal_value",
            "width": 150,
        },
        {
            "label": "Market Price",
            "fieldname": "market_price",
            "fieldtype": "Float",
            "width": 100,
        },
        {
            "label": "Accrued Interest",
            "fieldname": "accrued_interest",
            "fieldtype": "Float",
            "width": 100,
        },
        {
            "label": "Purchases Value",
            "fieldname": "purchases_value",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Sales Value",
            "fieldname": "sales_value",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Coupons Value",
            "fieldname": "copons_value",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Repayment Value",
            "fieldname": "repayment_value",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Market Value",
            "fieldname": "market_value",
            "fieldtype": "Currency",
            "width": 160,
        },
        {
            "label": "Gain/Loss Value",
            "fieldname": "gain_value",
            "fieldtype": "Currency",
            "width": 160,
        },
        {"label": "XIRR", "fieldname": "xirr", "fieldtype": "Percent", "width": 100},
    ]


# ---------- CORE DATA ----------


def get_data(portfolio, valuation_date):
    rows = []

    positions = get_positions(portfolio, valuation_date)

    if len(positions) > 100:
        frappe.throw("Too many bonds. Please filter portfolio.")

    for p in positions:
        isin = p["isin"]
        nominal = p["nominal"]

        # ---------- MARKET DATA ----------
        price = get_market_prices(isin, valuation_date)

        clean = price.get("market_price") or 0.0
        accrued = price.get("accrued_interest") or 0.0
        dirty = clean + accrued

        mv_clean = nominal * clean
        accrued_val = nominal * accrued
        total_val = nominal * dirty

        # ---------- FLOWS (CACHED) ----------
        if isin not in flows_cache:
            past = build_past_cashflows(isin, portfolio)
            future = build_future_cashflows(isin, valuation_date)

            # normalize once
            flows_cache[isin] = consolidate_flows(past + future)

        bond_cf = flows_cache[isin]

        if len(bond_cf) > 200:
            bond_xirr = None
            frappe.message_log("Too Many Lines on Cashflow: max 200")

        # ---------- BOND XIRR ----------
        bond_xirr = safe_xirr(bond_cf)

        # ---------- PORTFOLIO AGGREGATION ----------
        for d, amt in bond_cf.items():
            portfolio_cf[d] = portfolio_cf.get(d, 0.0) + amt

        rows.append(
            {
                "isin": isin,
                "bond_name": p.get("bond_name"),
                "nominal": nominal,
                "clean_price": clean,
                "accrued_interest": accrued,
                "dirty_price": dirty,
                "market_value_clean": mv_clean,
                "accrued_value": accrued_val,
                "total_value": total_val,
                "xirr": bond_xirr,
            }
        )

    portfolio_xirr = safe_xirr(portfolio_cf)

    return rows, portfolio_xirr


# ---------- TOTAL ROW ----------
"""

def make_total_row(data, portfolio_xirr):
    total_nominal = sum(d["nominal"] for d in data)
    total_clean_value = sum(d["market_value_clean"] for d in data)
    total_accrued = sum(d["accrued_value"] for d in data)
    total_value = sum(d["total_value"] for d in data)

    return {
        "isin": "TOTAL",
        "nominal": total_nominal,
        "market_value_clean": total_clean_value,
        "accrued_value": total_accrued,
        "total_value": total_value,
        "xirr": portfolio_xirr,
    }
"""

# ---------- HELPERS ----------

"""
def safe_xirr(cf_dict):
    try:
        if len(cf_dict) < 2:
            return None

        return xirr(cf_dict)
    except Exception:
        return None


def consolidate_flows(flows):
    out = {}

    for d, amt in flows:
        if not d or amt is None:
            continue

        out[d] = out.get(d, 0.0) + float(amt)

    return out
"""

# ---------- PLACEHOLDERS (you already have these) ----------
"""

def get_positions(portfolio):
    method = frappe.get_attr(
        "bond_management.bond_management.doctype.bond_transaction.bond_transaction.get_position"
    )
    return method(portfolio=portfolio)


# currently does not exist one below is only for testing
def get_market_price(isin, valuation_date):
    method = frappe.get_attr(
        "bond_management.bond_management.doctype.bond_market_prices.bond_market_prices.market_price"
    )
    return method(isin=isin, valuation_date=valuation_date)


# currently does not exist one below is only for testing
def build_past_cashflows(isin, portfolio):
    method = frappe.get_attr(
        "bond_management.bond_management.doctype.bond_statement.bond_statement.build_future_cashflows"
    )
    return method(isin=isin, portfolio=portfolio)


def build_future_cashflows(isin, valuation_date):
    method = frappe.get_attr(
        "bond_management.bond_management.doctype.bond_statement.bond_statement.build_future_cashflows"
    )
    return method(isin=isin, valuation_date=valuation_date)

"""
