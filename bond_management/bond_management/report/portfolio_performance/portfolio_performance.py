# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import escape_html, getdate

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_schedule,
    unit_accrued_interest_from_bond,
)
from bond_management.bond_management.utils.exchange_rate import (
    REPORTING_CURRENCY,
    convert_cashflows,
    get_rate_for_date,
)
from bond_management.bond_management.utils.financial import quantize_money, to_decimal
from bond_management.bond_management.utils.performance import load_portfolio_performance_context
from bond_management.bond_management.utils.portfolio import get_ledger_position_from_transactions
from bond_management.bond_management.utils.validation import required_string
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
    """Return native-currency and USD performance values for one portfolio."""
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        frappe.throw(_("Report filters must be an object"))

    portfolio, valuation_date = validate_report_inputs(
        filters.get("portfolio"), filters.get("valuation_date")
    )

    columns = get_columns()
    (
        data,
        combined_cashflow,
        combined_future_cashflow,
        combined_reporting_cashflow,
        combined_future_reporting_cashflow,
    ) = get_data(portfolio, valuation_date)

    data = list(data)
    if data:
        data.append(
            make_total_row(
                data,
                combined_cashflow,
                combined_future_cashflow,
                combined_reporting_cashflow,
                combined_future_reporting_cashflow,
            )
        )
    return columns, data


@frappe.whitelist(methods=["POST"])
def get_xirr_cashflows(portfolio: str, valuation_date: str, isin: str, xirr_type: str) -> list[dict]:
    """Return native cash flows behind a report XIRR value for spreadsheet review."""
    portfolio, valuation_date = validate_report_inputs(portfolio, valuation_date)

    isin = required_string(isin, "ISIN")
    xirr_type = required_string(xirr_type, "XIRR type")
    if xirr_type not in {"past", "future"}:
        frappe.throw(_("Invalid XIRR type"))

    context = load_portfolio_performance_context(portfolio, valuation_date)
    if isin == "TOTAL":
        (
            _data,
            past_cashflows,
            future_cashflows,
            _reporting_past_cashflows,
            _reporting_future_cashflows,
        ) = get_data(portfolio, valuation_date, context=context)
        cashflows = past_cashflows if xirr_type == "past" else future_cashflows
    else:
        portfolio_isins = set(context["isins"])
        if isin not in portfolio_isins:
            frappe.throw(
                f"ISIN {frappe.bold(escape_html(isin))} is not in this portfolio on or before the valuation date"
            )
        if not frappe.has_permission("Bond Master", "read", doc=isin):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

        bond = context["bonds"][isin]
        transactions = context["transactions"][isin]
        quantity = get_ledger_position_from_transactions(transactions, valuation_date)
        if getdate(bond.maturity_date) <= getdate(valuation_date):
            quantity = to_decimal(0)
        market_price = context["market_prices"].get(isin)
        terminal_market_price = get_terminal_market_price(isin, valuation_date, quantity, market_price)
        if xirr_type == "past":
            cashflows = create_past_cash_flows(
                isin=isin,
                date=valuation_date,
                market_price=terminal_market_price,
                portfolio=portfolio,
                bond_doc=bond,
                transactions=transactions,
            )
        elif not quantity:
            cashflows = []
        else:
            cashflows = create_future_cash_flows(
                isin,
                valuation_date,
                terminal_market_price,
                quantity=quantity,
                bond_doc=bond,
            )

    return [
        {
            "isin": cashflow["bond"],
            "transaction_type": cashflow["type"],
            "date": getdate(cashflow["date"]).isoformat(),
            # This endpoint is a spreadsheet/clipboard serialization boundary;
            # the underlying cash-flow calculations remain Decimal-based.
            "amount": round_cashflow_amount(cashflow["amount"]),
            "quantity": float(cashflow["quantity"]),
            "rate": round_cashflow_amount(to_decimal(cashflow["amount"]) / to_decimal(cashflow["quantity"])),
        }
        for cashflow in sorted(
            cashflows,
            key=lambda cashflow: (getdate(cashflow["date"]), float(cashflow["amount"])),
        )
        if to_decimal(cashflow["amount"]) != 0
    ]


def validate_report_inputs(portfolio, valuation_date):
    portfolio = required_string(portfolio, "Portfolio")
    valuation_date = required_string(valuation_date, "Valuation Date")
    if not frappe.has_permission("Bond Portfolio", "read", doc=portfolio):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    if not frappe.db.exists("Bond Portfolio", portfolio):
        frappe.throw(f"Bond Portfolio {frappe.bold(escape_html(portfolio))} does not exist")

    return portfolio, getdate(valuation_date)


def get_terminal_market_price(isin, valuation_date, quantity, market_price):
    """Require a valid quote only when a position still has market exposure."""
    if quantity and market_price is None:
        frappe.throw(
            f"No market price found for {frappe.bold(escape_html(isin))} on or before {valuation_date}"
        )
    if quantity and to_decimal(market_price) <= 0:
        frappe.throw(f"Market price for {frappe.bold(escape_html(isin))} must be greater than zero")

    # A closed/matured position needs no artificial terminal valuation. Zero is
    # passed only to the cash-flow builder so it omits that zero-value line.
    return to_decimal(market_price) if market_price is not None else to_decimal(0)


def calculate_future_xirr_from_cashflows(isin, valuation_date, cashflows, historical_guess=None):
    """Calculate future XIRR with the same bounded historical guess as the utility."""
    guess = historical_guess
    if guess is not None:
        guess = float(to_decimal(guess) / to_decimal(100))
    else:
        guess = get_last_xirr_guess(isin, valuation_date)
    if guess is None:
        guess = DEFAULT_XIRR_GUESS
    guess = max(min(guess, 1.0), -0.5)
    return calculate_xirr(consolidate_cashflows(cashflows), guess)


# ---------- COLUMNS ----------


def get_columns() -> list[dict]:
    """Return the native and reporting-currency report columns."""
    return [
        {
            "label": _("ISIN"),
            "fieldname": "isin",
            "fieldtype": "Link",
            "options": "Bond Master",
            "width": 140,
        },
        {"label": _("CCY"), "fieldname": "currency", "width": 60},
        {"label": _("Rpt. CCY"), "fieldname": "reporting_currency", "width": 75},
        {"label": _("FX Rate"), "fieldname": "exchange_rate", "fieldtype": "Float", "width": 90},
        {
            "label": _("Prin. Factor"),
            "fieldname": "principal_factor",
            "fieldtype": "Float",
            "width": 110,
        },
        {
            "label": _("Nominal Value"),
            "fieldname": "nominal_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": _("Nominal Value (USD)"),
            "fieldname": "nominal_value_usd",
            "fieldtype": "Currency",
            "options": "reporting_currency",
            "width": 145,
        },
        {
            "label": _("Purchases Value"),
            "fieldname": "purchases_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": _("Purchases Value (USD)"),
            "fieldname": "purchases_value_usd",
            "fieldtype": "Currency",
            "options": "reporting_currency",
            "width": 145,
        },
        {
            "label": _("Proceeds Value"),
            "fieldname": "proceeds_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
            "description": _("Sales, coupon payments and principal amortisation received."),
        },
        {
            "label": _("Proceeds Value (USD)"),
            "fieldname": "proceeds_value_usd",
            "fieldtype": "Currency",
            "options": "reporting_currency",
            "width": 145,
            "description": _("USD equivalent of sales, coupons and principal amortisation received."),
        },
        {
            "label": _("Market Value"),
            "fieldname": "market_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": _("Market Value (USD)"),
            "fieldname": "market_value_usd",
            "fieldtype": "Currency",
            "options": "reporting_currency",
            "width": 145,
        },
        {
            "label": _("Gain Value"),
            "fieldname": "gain_value",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": _("Gain Value (USD)"),
            "fieldname": "gain_value_usd",
            "fieldtype": "Currency",
            "options": "reporting_currency",
            "width": 145,
        },
        {"label": _("XIRR"), "fieldname": "xirr", "fieldtype": "Percent", "width": 80},
        {
            "label": _("Future XIRR"),
            "fieldname": "future_xirr",
            "fieldtype": "Percent",
            "width": 105,
        },
        {"label": _("XIRR (USD)"), "fieldname": "xirr_usd", "fieldtype": "Percent", "width": 95},
        {
            "label": _("Future XIRR (USD)"),
            "fieldname": "future_xirr_usd",
            "fieldtype": "Percent",
            "width": 120,
        },
    ]


# ---------- CORE DATA ----------


def get_data(portfolio, valuation_date, context=None):
    rows = []
    valuation_date = getdate(valuation_date)
    context = context or load_portfolio_performance_context(portfolio, valuation_date)

    combined_cashflow = []
    combined_future_cashflow = []
    combined_reporting_cashflow = []
    combined_future_reporting_cashflow = []

    for isin in context["isins"]:
        bond = context["bonds"][isin]
        transactions = context["transactions"][isin]
        quantity = get_ledger_position_from_transactions(transactions, valuation_date)
        if getdate(bond.maturity_date) <= valuation_date:
            quantity = to_decimal(0)

        # ---------- MASTER DATA ----------
        currency = bond.get("currency")
        face_value_per_unit = to_decimal(bond.get("face_value_per_unit"))
        exchange_rates = context.get("exchange_rates", {})
        valuation_exchange_rate = get_rate_for_date(
            exchange_rates,
            currency,
            valuation_date,
            portfolio=portfolio,
        )

        # ---------- MARKET DATA ----------
        market_price = context["market_prices"].get(isin)
        terminal_market_price = get_terminal_market_price(isin, valuation_date, quantity, market_price)
        accrued_interest = unit_accrued_interest_from_bond(bond, valuation_date)
        market_value = quantity * (
            face_value_per_unit * to_decimal(terminal_market_price) / to_decimal(100) + accrued_interest
        )

        # ---------- CASHFLOW DATA ----------
        principal_factor = calculate_principal_factor_from_schedule(
            bond.get("principal_schedule"), valuation_date
        )
        nominal_value = quantity * face_value_per_unit * principal_factor

        cashflows = create_past_cash_flows(
            isin=isin,
            date=valuation_date,
            market_price=terminal_market_price,
            portfolio=portfolio,
            bond_doc=bond,
            transactions=transactions,
        )
        combined_cashflow.extend(cashflows)
        reporting_cashflows = convert_cashflows(
            cashflows,
            exchange_rates,
            portfolio=portfolio,
            currency=currency,
        )
        combined_reporting_cashflow.extend(reporting_cashflows)

        totals = defaultdict(Decimal)
        reporting_totals = defaultdict(Decimal)
        for line in cashflows:
            totals[line.get("type")] += line.get("amount") or 0
        for line in reporting_cashflows:
            reporting_totals[line.get("type")] += line.get("amount") or 0

        purchases_value = -totals["purchase"]
        proceeds_value = totals["sale"] + totals["coupon"] + totals["amortisation"]
        purchases_value_usd = -reporting_totals["purchase"]
        proceeds_value_usd = (
            reporting_totals["sale"] + reporting_totals["coupon"] + reporting_totals["amortisation"]
        )

        xirr = calculate_xirr(consolidate_cashflows(cashflows))
        xirr = xirr * 100.0 if xirr is not None else 0.0
        xirr_usd = calculate_xirr(consolidate_cashflows(reporting_cashflows))
        xirr_usd = xirr_usd * 100.0 if xirr_usd is not None else 0.0

        if quantity:
            future_cashflows = create_future_cash_flows(
                isin=isin,
                date=valuation_date,
                market_price=terminal_market_price,
                quantity=quantity,
                bond_doc=bond,
            )
            future_xirr = calculate_future_xirr_from_cashflows(
                isin,
                valuation_date,
                future_cashflows,
                historical_guess=context["xirr_guesses"].get(isin),
            )
        else:
            future_xirr = None
            future_cashflows = []

        combined_future_cashflow.extend(future_cashflows)
        future_reporting_cashflows = convert_cashflows(
            future_cashflows,
            exchange_rates,
            portfolio=portfolio,
            currency=currency,
            rate_date=valuation_date,
        )
        combined_future_reporting_cashflow.extend(future_reporting_cashflows)

        future_xirr = future_xirr * 100.0 if future_xirr is not None else None
        future_xirr_usd = (
            calculate_future_xirr_from_cashflows(
                isin,
                valuation_date,
                future_reporting_cashflows,
                historical_guess=context["xirr_guesses"].get(isin),
            )
            if quantity
            else None
        )
        future_xirr_usd = future_xirr_usd * 100.0 if future_xirr_usd is not None else None

        market_value_usd = market_value * valuation_exchange_rate
        nominal_value_usd = nominal_value * valuation_exchange_rate

        rows.append(
            {
                "isin": isin,
                "currency": currency,
                "reporting_currency": REPORTING_CURRENCY,
                "exchange_rate": valuation_exchange_rate,
                "principal_factor": principal_factor,
                "nominal_value": quantize_money(nominal_value),
                "nominal_value_usd": quantize_money(nominal_value_usd),
                "purchases_value": quantize_money(purchases_value),
                "purchases_value_usd": quantize_money(purchases_value_usd),
                "proceeds_value": quantize_money(proceeds_value),
                "proceeds_value_usd": quantize_money(proceeds_value_usd),
                "market_value": quantize_money(market_value),
                "market_value_usd": quantize_money(market_value_usd),
                "gain_value": quantize_money(market_value + proceeds_value - purchases_value),
                "gain_value_usd": quantize_money(market_value_usd + proceeds_value_usd - purchases_value_usd),
                "xirr": xirr,
                "future_xirr": future_xirr,
                "xirr_usd": xirr_usd,
                "future_xirr_usd": future_xirr_usd,
            }
        )

    return (
        rows,
        combined_cashflow,
        combined_future_cashflow,
        combined_reporting_cashflow,
        combined_future_reporting_cashflow,
    )


# ---------- TOTAL ROW ----------


def make_total_row(
    data,
    combined_cashflow,
    combined_future_cashflow,
    combined_reporting_cashflow=None,
    combined_future_reporting_cashflow=None,
):
    currencies = {row["currency"] for row in data if row.get("currency")}
    single_native_currency = len(currencies) <= 1

    def sum_field(fieldname, fallback_fieldname=None):
        values = [row.get(fieldname, row.get(fallback_fieldname, 0)) for row in data]
        return quantize_money(sum((to_decimal(value) for value in values), Decimal(0)))

    native_values = {
        "nominal_value": sum_field("nominal_value") if single_native_currency else None,
        "purchases_value": sum_field("purchases_value") if single_native_currency else None,
        "proceeds_value": sum_field("proceeds_value") if single_native_currency else None,
        "market_value": sum_field("market_value") if single_native_currency else None,
        "gain_value": sum_field("gain_value") if single_native_currency else None,
    }
    reporting_values = {
        "nominal_value_usd": sum_field("nominal_value_usd", "nominal_value"),
        "purchases_value_usd": sum_field("purchases_value_usd", "purchases_value"),
        "proceeds_value_usd": sum_field("proceeds_value_usd", "proceeds_value"),
        "market_value_usd": sum_field("market_value_usd", "market_value"),
        "gain_value_usd": sum_field("gain_value_usd", "gain_value"),
    }

    cash_flows = consolidate_cashflows(cash_flows=combined_cashflow)
    xirr_value = calculate_xirr(cash_flows) if single_native_currency else None

    future_cash_flows = consolidate_cashflows(cash_flows=combined_future_cashflow)
    future_xirr = calculate_xirr(future_cash_flows) if single_native_currency else None

    reporting_cash_flows = consolidate_cashflows(
        cash_flows=combined_reporting_cashflow
        if combined_reporting_cashflow is not None
        else combined_cashflow
    )
    reporting_xirr = calculate_xirr(reporting_cash_flows)

    future_reporting_cash_flows = consolidate_cashflows(
        cash_flows=combined_future_reporting_cashflow
        if combined_future_reporting_cashflow is not None
        else combined_future_cashflow
    )
    future_reporting_xirr = calculate_xirr(future_reporting_cash_flows)

    return {
        "isin": "TOTAL",
        "currency": currencies.pop() if single_native_currency and currencies else None,
        "reporting_currency": REPORTING_CURRENCY,
        **native_values,
        **reporting_values,
        "xirr": xirr_value * 100 if xirr_value is not None else 0.0,
        "future_xirr": future_xirr * 100 if future_xirr is not None else None,
        "xirr_usd": reporting_xirr * 100 if reporting_xirr is not None else 0.0,
        "future_xirr_usd": future_reporting_xirr * 100 if future_reporting_xirr is not None else None,
    }
