# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate
from pyxirr import xirr
from collections import defaultdict
from bond_management.bond_management.utils.performance import (
    get_transactions,
    get_market_price,
    get_distinct_isins,
)
from bond_management.bond_management.utils.accrual import unit_accrued_interest, calculate_principal_factor
from bond_management.bond_management.utils.xirr import create_past_cash_flows, get_position, consolidate_cashflows, calculate_past_xirr

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
    data, combined_cashflow = get_data(portfolio, valuation_date)

    # Add summary row
    if data:
        total_row = make_total_row(data, combined_cashflow)
        #data.append({})
        data.append(total_row)
    return columns, data



# ---------- COLUMNS ----------


def get_columns() -> list[dict]:
    """Return columns for the report.

    One field definition per column, just like a DocType field definition.
    """
    return [
        {"label": "ISIN", "fieldname": "isin", "fieldtype": "Link", "options": "Bond Master", "width": 140},
        {"label": "Currency", "fieldname": "currency", "width": 90},
        {"label": "Face Value/Unit", "fieldname": "face_value_per_unit", "width": 150},
        {"label": "Princlipal Factor", "fieldname": "principal_factor", "fieldtype": "Float", "width": 150},
        {"label": "Number of Units", "fieldname": "quantity", "width": 150},       
        {"label": "Nominal Value", "fieldname": "nominal_value", "fieldtype": "Currency", "options": "currency", "width": 150},
        {"label": "Market Price", "fieldname": "market_price", "fieldtype": "Float", "width": 100},
        {"label": "Accrued Interest", "fieldname": "accrued_interest", "fieldtype": "Float", "width": 100},
        {"label": "Purchases Value", "fieldname": "purchases_value", "fieldtype": "Currency", "options": "currency", "width": 120},
        {"label": "Sales Value", "fieldname": "sales_value", "fieldtype": "Currency", "options": "currency",  "width": 120},
        {"label": "Coupons Value", "fieldname": "coupons_value", "fieldtype": "Currency", "options": "currency",  "width": 120},
        {"label": "Amotisation Value", "fieldname": "amortisation_value", "fieldtype": "Currency", "options": "currency",  "width": 120},
        {"label": "Market Value", "fieldname": "market_value", "fieldtype": "Currency", "options": "currency",  "width": 160},
        {"label": "Gain Value", "fieldname": "gain_value", "fieldtype": "Currency", "options": "currency",  "width": 160},
        {"label": "XIRR", "fieldname": "xirr", "fieldtype": "Percent", "width": 150},
    ]


# ---------- CORE DATA ----------


def get_data(portfolio, valuation_date):
    rows = []

    isins = get_distinct_isins(portfolio=portfolio, date=valuation_date)

    combined_cashflow = []
    for bond in isins:

        # ---------- TRANSACTION DATA ----------
        isin = bond["isin"]

        quantity = get_position(isin=isin, statement_date=valuation_date, portfolio_name=portfolio)

        # ---------- MASTER DATA ----------
        bond = frappe.qb.get_query("Bond Master", fields=["currency", "face_value_per_unit"]).run(as_dict=True)[0]
        currency = bond.get("currency")
        face_value_per_unit = bond.get("face_value_per_unit")


        # ---------- MARKET DATA ----------
        market_price = get_market_price(isin=isin, valuation_date=valuation_date)
        accrued_interest = unit_accrued_interest(isin=isin, settlement_date=valuation_date)
        market_value = quantity * (market_price + accrued_interest)

        # ---------- CASHFLOW DATA ----------
        principal_factor = calculate_principal_factor(isin=isin, date=valuation_date)
        nominal_value = quantity * face_value_per_unit * principal_factor

        cashflows = create_past_cash_flows(isin=isin, date=valuation_date, market_price=market_price, portfolio=portfolio)
        combined_cashflow.extend(cashflows)

        totals = defaultdict(float)

        for line in cashflows:
            totals[line.get("type")] = totals[line.get("type")] + line.get("amount") or 0

        # access:
        coupons_value = totals["coupon"]
        amortisation_value = totals["amortisation"]
        purchases_value = -totals["purchase"]
        sales_value = totals["sale"]

        xirr_abs = calculate_past_xirr(isin=isin, date=valuation_date, market_price=market_price, portfolio=portfolio)
        if xirr_abs:
            xirr = xirr_abs * 100

        else:
            xirr = None

        rows.append(
            {
                "isin": isin,
                "currency": currency,
                "face_value_per_unit": face_value_per_unit,
                "principal_factor": principal_factor,
                "quantity": quantity,
                "nominal_value": nominal_value,
                "market_price": market_price,
                "accrued_interest": accrued_interest,
                "purchases_value": purchases_value,
                "sales_value": sales_value,
                "coupons_value": coupons_value,
                "amortisation_value": amortisation_value,
                "market_value": market_value,
                "gain_value": (market_value + amortisation_value + coupons_value + sales_value - purchases_value),
                "xirr": xirr,
            }
        )

    return rows, combined_cashflow


# ---------- TOTAL ROW ----------


def make_total_row(data, combined_cashflow):
    nominal_value = sum(d["nominal_value"] for d in data)
    purchases_value = sum(d["purchases_value"] for d in data)   
    sales_value = sum(d["sales_value"] for d in data)
    coupons_value = sum(d["coupons_value"] for d in data)
    amortisation_value = sum(d["amortisation_value"] for d in data)
    market_value = sum(d["market_value"] for d in data)
    gain_value = sum(d["gain_value"] for d in data)
    
    #print(combined_cashflow)
    cash_flows = consolidate_cashflows(cash_flows=combined_cashflow)

    xirr_value = xirr(cash_flows, guess=0.1)*100

    #xirr_value = 0.0

    return {
        "isin": "TOTAL",
        "currency": "USD",  # hardcoded for now!
        "nominal_value": nominal_value,
        "purchases_value": purchases_value,
        "sales_value": sales_value,
        "coupons_value": coupons_value,
        "amortisation_value": amortisation_value,
        "market_value": market_value,
        "gain_value": gain_value,        
        "xirr": xirr_value,
    }


