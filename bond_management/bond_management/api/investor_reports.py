"""Stable report projections for the investor SPA."""

import frappe
from frappe import _
from frappe.desk.query_report import get_report_doc
from frappe.model.meta import get_field_precision
from frappe.utils import getdate, today

from bond_management.bond_management.report.bond_yield_comparison.bond_yield_comparison import (
    execute as execute_bond_yield_comparison,
)
from bond_management.bond_management.report.bond_yield_comparison.bond_yield_comparison import (
    get_readable_isins,
)
from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    execute as execute_portfolio_performance,
)
from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    get_xirr_cashflows,
)
from bond_management.bond_management.utils.investor_ui import require_investor_ui_access
from bond_management.bond_management.utils.validation import optional_string, required_string

PORTFOLIO_PERFORMANCE_REPORT = "Portfolio Performance"
BOND_YIELD_COMPARISON_REPORT = "Bond Yield Comparison"
PORTFOLIO_PERFORMANCE_COLUMN_FIELDS = (
    "isin",
    "currency",
    "principal_factor",
    "nominal_value",
    "purchases_value",
    "proceeds_value",
    "market_value",
    "market_value_usd",
    "gain_value",
    "xirr",
    "xirr_usd",
    "future_xirr",
)
PORTFOLIO_PERFORMANCE_ROW_FIELDS = (
    "isin",
    "currency",
    "reporting_currency",
    "principal_factor",
    "nominal_value",
    "purchases_value",
    "proceeds_value",
    "market_value",
    "market_value_usd",
    "gain_value",
    "xirr",
    "xirr_usd",
    "future_xirr",
)
PORTFOLIO_CASHFLOW_FIELDS = (
    "isin",
    "transaction_type",
    "date",
    "currency",
    "amount",
    "quantity",
    "rate",
)
BOND_YIELD_COMPARISON_FIELDS = (
    "date",
    "isin",
    "currency",
    "market_price",
    "future_xirr",
)

_NUMERIC_FIELD_TYPES = {"Currency", "Float", "Percent"}
_CASHFLOW_ACTIONS = {
    "xirr": {"xirr_type": "past", "cashflow_currency": "native"},
    "xirr_usd": {"xirr_type": "past", "cashflow_currency": "reporting"},
    "future_xirr": {"xirr_type": "future", "cashflow_currency": "native"},
}

YIELD_COMPARISON_CHART = {
    "x_field": "date",
    "value_field": "future_xirr",
    "series_field": "isin",
    "gap_policy": "preserve",
}


@frappe.whitelist(methods=["GET"])
def get_portfolio_performance(portfolio: str, valuation_date: str) -> dict:
    """Return the authoritative report through a fixed investor projection."""
    require_investor_ui_access()
    filters = _authorized_filters(portfolio, valuation_date)
    columns, rows = execute_portfolio_performance(filters)

    return {
        "report": {
            "filters": filters,
            "columns": _project_columns(columns),
            "rows": [_project_fields(row, PORTFOLIO_PERFORMANCE_ROW_FIELDS) for row in rows],
            "chart": None,
        }
    }


@frappe.whitelist(methods=["GET"])
def get_portfolio_performance_cashflows(
    portfolio: str,
    valuation_date: str,
    isin: str,
    xirr_type: str,
    cashflow_currency: str | None = None,
) -> dict:
    """Return allow-listed cash flows behind one authoritative report value."""
    require_investor_ui_access()
    filters = _authorized_filters(portfolio, valuation_date)
    cashflows = get_xirr_cashflows(
        filters["portfolio"],
        filters["valuation_date"],
        isin,
        xirr_type,
        cashflow_currency,
    )
    return {"cashflows": [_project_fields(row, PORTFOLIO_CASHFLOW_FIELDS) for row in cashflows]}


@frappe.whitelist(methods=["GET"])
def get_bond_yield_comparison(
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict:
    """Return persisted market yields through a fixed investor projection."""
    require_investor_ui_access()
    get_report_doc(BOND_YIELD_COMPARISON_REPORT)

    filters = _yield_comparison_filters(from_date, to_date)
    columns, rows = execute_bond_yield_comparison(filters)
    return {
        "report": {
            "filters": filters,
            "columns": [_project_yield_column(column) for column in columns],
            "rows": [_project_fields(row, BOND_YIELD_COMPARISON_FIELDS) for row in rows],
            "chart": dict(YIELD_COMPARISON_CHART),
        }
    }


@frappe.whitelist(methods=["GET"])
def get_yield_comparison_defaults() -> dict:
    """Return permission-scoped default date bounds without running the report."""
    require_investor_ui_access()
    get_report_doc(BOND_YIELD_COMPARISON_REPORT)

    return {
        "filters": {
            "from_date": _oldest_readable_yield_date(),
            "to_date": today(),
        }
    }


def _authorized_filters(portfolio, valuation_date) -> dict:
    portfolio = required_string(portfolio, "Portfolio")
    valuation_date = required_string(valuation_date, "Valuation Date")

    # Reuse Frappe's standard Report-role and reference-DocType report checks.
    get_report_doc(PORTFOLIO_PERFORMANCE_REPORT)
    _require_readable_portfolio(portfolio)

    return {
        "portfolio": portfolio,
        "valuation_date": getdate(valuation_date).isoformat(),
    }


def _yield_comparison_filters(from_date, to_date) -> dict:
    from_date = optional_string(from_date, "From Date")
    to_date = optional_string(to_date, "To Date")
    return {"from_date": from_date, "to_date": to_date}


def _oldest_readable_yield_date() -> str | None:
    readable_isins = get_readable_isins(None)
    if not readable_isins:
        return None

    dates = frappe.qb.get_query(
        "Bond Market Date",
        fields=["date"],
        filters={"bond_market_prices.isin": ["in", readable_isins]},
        order_by="date asc",
        limit=1,
        distinct=True,
        ignore_permissions=False,
    ).run(pluck=True)
    return getdate(dates[0]).isoformat() if dates else None


def _require_readable_portfolio(portfolio: str) -> None:
    readable = frappe.qb.get_query(
        "Bond Portfolio",
        fields=["name"],
        filters={"name": portfolio},
        limit=1,
        ignore_permissions=False,
    ).run(pluck=True)
    if not readable:
        frappe.throw(_("You are not permitted to read this portfolio."), frappe.PermissionError)


def _project_columns(columns: list[dict]) -> list[dict]:
    allowed = set(PORTFOLIO_PERFORMANCE_COLUMN_FIELDS)
    return [_project_column(column) for column in columns if column.get("fieldname") in allowed]


def _project_column(column: dict) -> dict:
    fieldtype = column.get("fieldtype") or "Data"
    normalized = frappe._dict(column)
    normalized.fieldtype = fieldtype
    precision = get_field_precision(normalized) if fieldtype in _NUMERIC_FIELD_TYPES else None

    return {
        "fieldname": column["fieldname"],
        "label": column.get("label") or column["fieldname"],
        "fieldtype": fieldtype,
        "options": column.get("options"),
        "description": column.get("description"),
        "precision": precision,
        "cashflow_action": _CASHFLOW_ACTIONS.get(column["fieldname"]),
    }


def _project_yield_column(column: dict) -> dict:
    projected = _project_column(column)
    projected.pop("cashflow_action")
    return projected


def _project_fields(row: dict, fields: tuple[str, ...]) -> dict:
    return {field: row.get(field) for field in fields}
