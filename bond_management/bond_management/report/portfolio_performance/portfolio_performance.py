# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import datetime
from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.desk.query_report import get_report_doc
from frappe.utils import add_years, escape_html, getdate
from frappe.utils.data import DateTimeLikeObject

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_bond,
    calculate_quantity_factor_from_bond,
    unit_accrued_interest_from_bond,
)
from bond_management.bond_management.utils.exchange_rate import (
    REPORTING_CURRENCY,
    convert_cashflows,
    get_rate_for_date,
)
from bond_management.bond_management.utils.financial import DecimalInput, quantize_money, to_decimal
from bond_management.bond_management.utils.investor_access import require_readable_portfolio
from bond_management.bond_management.utils.performance import load_portfolio_performance_context
from bond_management.bond_management.utils.portfolio import get_ledger_position_from_transactions
from bond_management.bond_management.utils.validation import optional_string, required_string
from bond_management.bond_management.utils.xirr import (
    apply_withholding_tax,
    bounded_xirr_guess,
    calculate_xirr,
    consolidate_cashflows,
    create_future_cash_flows,
    create_past_cash_flows,
    get_last_xirr_guess,
    round_cashflow_amount,
)

XIRR_PRECISION = 3
REPORTING_ONLY_FIELDS = {"market_value_usd", "xirr_usd", "expected_coupons_next_year_usd"}

# ---------- ENTRY POINT ----------


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Return native-currency and USD performance values for one readable portfolio.

    Money is quantized to four places; XIRR columns are percents.
    """
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        frappe.throw(_("Report filters must be an object"))

    portfolio, valuation_date = validate_report_inputs(
        filters.get("portfolio"), filters.get("valuation_date")
    )

    data, combined_cashflow, combined_future_cashflow, combined_reporting_cashflow, _future_reporting = (
        get_data(portfolio, valuation_date)
    )

    data = list(data)
    columns = get_columns(has_non_reporting_currency(data))
    if data:
        data.append(
            make_total_row(data, combined_cashflow, combined_future_cashflow, combined_reporting_cashflow)
        )
    return columns, data


@frappe.whitelist(methods=["POST"])
def get_xirr_cashflows(
    portfolio: str,
    valuation_date: str,
    isin: str,
    xirr_type: str,
    cashflow_currency: str | None = None,
) -> list[dict]:
    """Return native or reporting-currency cash flows behind a report XIRR."""
    # This helper is directly whitelisted by the Desk report JavaScript, so the
    # wrapper's report-role check must not be its only authorization boundary.
    get_report_doc("Portfolio Performance")
    portfolio, valuation_date = validate_report_inputs(portfolio, valuation_date)

    isin = required_string(isin, "ISIN")
    xirr_type = required_string(xirr_type, "XIRR type")
    if xirr_type not in {"past", "future"}:
        frappe.throw(_("Invalid XIRR type"))
    cashflow_currency = optional_string(cashflow_currency, "Cash-flow currency") or "native"
    if cashflow_currency not in {"native", "reporting"}:
        frappe.throw(_("Invalid cash-flow currency"))

    context = load_portfolio_performance_context(portfolio, valuation_date)
    if isin == "TOTAL":
        (
            data,
            past_cashflows,
            future_cashflows,
            reporting_past_cashflows,
            reporting_future_cashflows,
        ) = get_data(portfolio, valuation_date, context=context)
        if cashflow_currency == "native" and len({row["currency"] for row in data}) > 1:
            frappe.throw(_("Native TOTAL cash flows are unavailable for a mixed-currency portfolio"))
        if cashflow_currency == "reporting":
            cashflows = reporting_past_cashflows if xirr_type == "past" else reporting_future_cashflows
            currency = REPORTING_CURRENCY
        else:
            cashflows = past_cashflows if xirr_type == "past" else future_cashflows
            currency = data[0]["currency"] if data else None
    else:
        portfolio_isins = set(context["isins"])
        if isin not in portfolio_isins:
            frappe.throw(
                _("ISIN {0} is not in this portfolio on or before the valuation date").format(
                    frappe.bold(escape_html(isin))
                )
            )
        if not frappe.has_permission("Bond Master", "read", doc=isin):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

        bond = context["bonds"][isin]
        _quantity, _terminal_price, past, future = _bond_cashflows(
            portfolio, isin, context, valuation_date, xirr_type=xirr_type
        )
        cashflows = past if xirr_type == "past" else future
        currency = bond.currency
        if cashflow_currency == "reporting":
            cashflows = _reporting_cashflows(cashflows, bond, context, valuation_date, xirr_type=xirr_type)
            currency = REPORTING_CURRENCY

    return [
        {
            "isin": cashflow["bond"],
            "transaction_type": cashflow["type"],
            "date": getdate(cashflow["date"]).isoformat(),
            "currency": currency,
            # This endpoint is a spreadsheet/clipboard serialization boundary;
            # the underlying cash-flow calculations remain Decimal-based.
            "amount": round_cashflow_amount(cashflow["amount"]),
            "quantity": float(cashflow["quantity"]),
            "rate": _cashflow_rate(cashflow["amount"], cashflow["quantity"]),
        }
        for cashflow in sorted(
            cashflows,
            key=lambda cashflow: (getdate(cashflow["date"]), float(cashflow["amount"])),
        )
        if to_decimal(cashflow["amount"]) != 0
    ]


def validate_report_inputs(portfolio: object, valuation_date: object) -> tuple[str, datetime.date]:
    """Require a readable portfolio and a valuation date string, which is returned as a date."""
    portfolio = required_string(portfolio, "Portfolio")
    valuation_date = required_string(valuation_date, "Valuation Date")
    require_readable_portfolio(portfolio)
    return portfolio, getdate(valuation_date)


def _cashflow_rate(amount: DecimalInput, quantity: DecimalInput) -> float | None:
    quantity = to_decimal(quantity)
    if not quantity:
        return None
    return round_cashflow_amount(to_decimal(amount) / quantity)


def get_terminal_market_price(
    isin: str, valuation_date: datetime.date, quantity: Decimal, market_price: DecimalInput
) -> Decimal:
    """Require a valid quote only when a position still has market exposure.

    Returns the price per 100 of original face value, or zero for a closed position without a quote.
    """
    if quantity and market_price is None:
        frappe.throw(
            _("No market price found for {0} on or before {1}").format(
                frappe.bold(escape_html(isin)), valuation_date
            )
        )
    if quantity and to_decimal(market_price) <= 0:
        frappe.throw(
            _("Market price for {0} must be greater than zero").format(frappe.bold(escape_html(isin)))
        )

    # A closed/matured position needs no artificial terminal valuation. Zero is
    # passed only to the cash-flow builder so it omits that zero-value line.
    return to_decimal(market_price) if market_price is not None else to_decimal(0)


def calculate_future_xirr_from_cashflows(
    isin: str,
    valuation_date: DateTimeLikeObject,
    cashflows: Iterable[Mapping[str, Any]],
    historical_guess: float | None = None,
) -> float | None:
    """Calculate future XIRR, as a decimal rate, with the same bounded historical guess as the utility."""
    guess = historical_guess if historical_guess is not None else get_last_xirr_guess(isin, valuation_date)
    return calculate_xirr(consolidate_cashflows(cashflows), bounded_xirr_guess(guess))


# ---------- COLUMNS ----------


def get_columns(include_reporting_currency_columns: bool = True) -> list[dict]:
    """Return native columns and reporting columns when they add information."""

    def money(label: str, fieldname: str, width: int = 145, options: str = "currency", **extra: Any) -> dict:
        return {
            "label": label,
            "fieldname": fieldname,
            "fieldtype": "Currency",
            "options": options,
            "width": width,
            **extra,
        }

    def percent(label: str, fieldname: str, width: int) -> dict:
        return {
            "label": label,
            "fieldname": fieldname,
            "fieldtype": "Percent",
            "precision": XIRR_PRECISION,
            "width": width,
        }

    columns = [
        {
            "label": _("ISIN"),
            "fieldname": "isin",
            "fieldtype": "Link",
            "options": "Bond Master",
            "width": 140,
        },
        {"label": _("CCY"), "fieldname": "currency", "width": 60},
        {
            "label": _("Prin. Factor"),
            "fieldname": "principal_factor",
            "fieldtype": "Float",
            "width": 120,
            "disable_total": True,
        },
        money(_("Nominal Value"), "nominal_value"),
        money(_("Purchases Value"), "purchases_value"),
        money(
            _("Proceeds Value"),
            "proceeds_value",
            description=_("Sales, coupon payments and principal amortisation received."),
        ),
        money(_("Market Value"), "market_value"),
        money(_("Market Value (USD)"), "market_value_usd", 155, "reporting_currency"),
        money(_("Gain Value"), "gain_value"),
        percent(_("XIRR"), "xirr", 85),
        percent(_("XIRR (USD)"), "xirr_usd", 100),
        percent(_("Future XIRR"), "future_xirr", 110),
        money(
            _("Expected Coupons (Next Year)"),
            "expected_coupons_next_year",
            190,
            description=_("Coupon payments after the valuation date through exactly one year after it."),
        ),
        money(
            _("Expected Coupons (Next Year) (USD)"),
            "expected_coupons_next_year_usd",
            210,
            "reporting_currency",
        ),
    ]
    if include_reporting_currency_columns:
        return columns
    return [column for column in columns if column["fieldname"] not in REPORTING_ONLY_FIELDS]


def has_non_reporting_currency(data: Iterable[Mapping[str, Any]]) -> bool:
    """Return whether the report contains a bond outside the reporting currency."""
    return any(row.get("currency") and row.get("currency") != REPORTING_CURRENCY for row in data)


def expected_coupon_value(
    cashflows: Iterable[Mapping[str, Any]], valuation_date: DateTimeLikeObject
) -> Decimal:
    """Return coupons after valuation through the inclusive one-year cutoff, quantized to money precision."""
    valuation_date = getdate(valuation_date)
    cutoff_date = getdate(add_years(valuation_date, 1))
    return quantize_money(
        sum(
            (
                to_decimal(cashflow.get("amount"))
                for cashflow in cashflows
                if cashflow.get("type") == "coupon"
                and cashflow.get("date")
                and valuation_date < getdate(cashflow.get("date")) <= cutoff_date
            ),
            Decimal(0),
        )
    )


# ---------- CORE DATA ----------


def get_data(
    portfolio: str, valuation_date: DateTimeLikeObject, context: dict[str, Any] | None = None
) -> tuple[
    list[dict], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """Return report rows and the combined native past, native future, USD past and USD future cash flows."""
    rows = []
    valuation_date = getdate(valuation_date)
    context = context or load_portfolio_performance_context(portfolio, valuation_date)

    combined_cashflow = []
    combined_future_cashflow = []
    combined_reporting_cashflow = []
    combined_future_reporting_cashflow = []

    for isin in context["isins"]:
        bond = context["bonds"][isin]
        quantity, terminal_market_price, cashflows, future_cashflows = _bond_cashflows(
            portfolio, isin, context, valuation_date
        )

        # ---------- MASTER DATA ----------
        currency = bond.get("currency")
        face_value_per_unit = to_decimal(bond.get("face_value_per_unit"))
        exchange_rates = context.get("exchange_rates", {})
        valuation_exchange_rate = get_rate_for_date(
            exchange_rates,
            currency,
            valuation_date,
        )

        # ---------- MARKET DATA ----------
        # The bank deducts withholding tax before paying interest (decision 0011).
        accrued_interest = apply_withholding_tax(unit_accrued_interest_from_bond(bond, valuation_date), bond)
        quantity_factor = calculate_quantity_factor_from_bond(bond, valuation_date)
        effective_quantity = quantity * quantity_factor
        market_value = effective_quantity * (
            face_value_per_unit * to_decimal(terminal_market_price) / to_decimal(100) + accrued_interest
        )

        # ---------- CASHFLOW DATA ----------
        principal_factor = calculate_principal_factor_from_bond(bond, valuation_date)
        nominal_value = effective_quantity * face_value_per_unit * principal_factor

        combined_cashflow.extend(cashflows)
        reporting_cashflows = _reporting_cashflows(cashflows, bond, context, valuation_date, xirr_type="past")
        combined_reporting_cashflow.extend(reporting_cashflows)

        totals = defaultdict(Decimal)
        for line in cashflows:
            totals[line.get("type")] += line.get("amount") or 0

        purchases_value = -totals["purchase"]
        proceeds_value = totals["sale"] + totals["coupon"] + totals["amortisation"]

        xirr = _percent_value(calculate_xirr(consolidate_cashflows(cashflows)))
        xirr_usd = _percent_value(calculate_xirr(consolidate_cashflows(reporting_cashflows)))

        if quantity:
            future_xirr = calculate_future_xirr_from_cashflows(
                isin,
                valuation_date,
                future_cashflows,
                historical_guess=context["xirr_guesses"].get(isin),
            )
        else:
            future_xirr = None

        combined_future_cashflow.extend(future_cashflows)
        future_reporting_cashflows = _reporting_cashflows(
            future_cashflows, bond, context, valuation_date, xirr_type="future"
        )
        combined_future_reporting_cashflow.extend(future_reporting_cashflows)
        expected_coupons_next_year = expected_coupon_value(future_cashflows, valuation_date)
        expected_coupons_next_year_usd = expected_coupon_value(
            future_reporting_cashflows,
            valuation_date,
        )

        rows.append(
            {
                "isin": isin,
                "currency": currency,
                "reporting_currency": REPORTING_CURRENCY,
                "principal_factor": principal_factor,
                "nominal_value": quantize_money(nominal_value),
                "purchases_value": quantize_money(purchases_value),
                "proceeds_value": quantize_money(proceeds_value),
                "expected_coupons_next_year": expected_coupons_next_year,
                "expected_coupons_next_year_usd": expected_coupons_next_year_usd,
                "market_value": quantize_money(market_value),
                "market_value_usd": quantize_money(market_value * valuation_exchange_rate),
                "gain_value": quantize_money(market_value + proceeds_value - purchases_value),
                "xirr": xirr,
                "future_xirr": _percent_value(future_xirr),
                "xirr_usd": xirr_usd,
                "has_past_cashflows": bool(cashflows),
                "has_future_cashflows": bool(future_cashflows),
            }
        )

    return (
        rows,
        combined_cashflow,
        combined_future_cashflow,
        combined_reporting_cashflow,
        combined_future_reporting_cashflow,
    )


def _bond_cashflows(
    portfolio: str,
    isin: str,
    context: dict[str, Any],
    valuation_date: datetime.date,
    *,
    xirr_type: str | None = None,
) -> tuple[Decimal, Decimal, list[dict[str, Any]], list[dict[str, Any]]]:
    """Use the same position and terminal quote for report and export flows."""
    bond = context["bonds"][isin]
    transactions = context["transactions"][isin]
    quantity = get_ledger_position_from_transactions(transactions, valuation_date)
    if getdate(bond.maturity_date) <= getdate(valuation_date):
        quantity = to_decimal(0)
    terminal_price = get_terminal_market_price(
        isin, valuation_date, quantity, context["market_prices"].get(isin)
    )
    # Exports build only the requested series; reports need both.
    past = (
        create_past_cash_flows(
            isin=isin,
            date=valuation_date,
            market_price=terminal_price,
            bond_doc=bond,
            transactions=transactions,
        )
        if xirr_type != "future"
        else []
    )
    future = (
        create_future_cash_flows(
            isin=isin,
            date=valuation_date,
            market_price=terminal_price,
            quantity=quantity,
            bond_doc=bond,
        )
        if quantity and xirr_type != "past"
        else []
    )
    return quantity, terminal_price, past, future


def _reporting_cashflows(
    cashflows: Iterable[Mapping[str, Any]],
    bond: frappe._dict,
    context: dict[str, Any],
    valuation_date: datetime.date,
    *,
    xirr_type: str,
) -> list[dict[str, Any]]:
    # Past flows use their own historical dates; future flows use today's valuation.
    return convert_cashflows(
        cashflows,
        context.get("exchange_rates", {}),
        currency=bond.currency,
        rate_date=valuation_date if xirr_type == "future" else None,
    )


# ---------- TOTAL ROW ----------


def make_total_row(
    data: list[dict],
    combined_cashflow: list[dict[str, Any]],
    combined_future_cashflow: list[dict[str, Any]],
    combined_reporting_cashflow: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the TOTAL row; native totals and XIRRs are ``None`` for a mixed-currency portfolio."""
    currencies = {row["currency"] for row in data if row.get("currency")}
    single_native_currency = len(currencies) <= 1

    def sum_field(fieldname: str) -> Decimal:
        return quantize_money(sum((to_decimal(row.get(fieldname)) for row in data), Decimal(0)))

    native_values = {
        fieldname: sum_field(fieldname) if single_native_currency else None
        for fieldname in (
            "nominal_value",
            "purchases_value",
            "proceeds_value",
            "expected_coupons_next_year",
            "market_value",
            "gain_value",
        )
    }
    reporting_values = {
        "expected_coupons_next_year_usd": sum_field("expected_coupons_next_year_usd"),
        "market_value_usd": sum_field("market_value_usd"),
    }

    xirr_value = calculate_xirr(consolidate_cashflows(combined_cashflow)) if single_native_currency else None
    future_xirr = (
        calculate_xirr(consolidate_cashflows(combined_future_cashflow)) if single_native_currency else None
    )
    reporting_xirr = calculate_xirr(consolidate_cashflows(combined_reporting_cashflow))

    return {
        "isin": "TOTAL",
        "currency": currencies.pop() if single_native_currency and currencies else None,
        "reporting_currency": REPORTING_CURRENCY,
        **native_values,
        **reporting_values,
        "xirr": _percent_value(xirr_value),
        "future_xirr": _percent_value(future_xirr),
        "xirr_usd": _percent_value(reporting_xirr),
        "has_past_cashflows": bool(combined_cashflow),
        "has_future_cashflows": bool(combined_future_cashflow),
    }


def _percent_value(value: float | None) -> float | None:
    return value * 100 if value is not None else None
