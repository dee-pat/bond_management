# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from datetime import date as Date
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import getdate

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_bond,
    calculate_quantity_factor_from_bond,
    get_coupon_period,
)
from bond_management.bond_management.utils.coupon_schedule import (
    is_kenya_day_count_convention,
    year_fraction,
)
from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.investor_permissions import investor_portfolio_access
from bond_management.bond_management.utils.validation import optional_string, required_string


def execute(filters: dict | None = None):
    filters = validate_filters(filters)
    rows = get_data(filters)
    return get_columns(), rows + make_total_rows(rows)


def validate_filters(filters: dict | None) -> dict:
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        frappe.throw(_("Report filters must be an object"))

    from_date = parse_date_filter(filters.get("from_date"), "From Date")
    to_date = parse_date_filter(filters.get("to_date"), "To Date")
    if from_date and to_date and from_date > to_date:
        frappe.throw(_("From Date must be on or before To Date"))

    portfolio_name = required_string(filters.get("portfolio_name"), "Portfolio")
    if investor_portfolio_access(frappe.session.user, portfolio_name) is False:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    frappe.has_permission("Bond Portfolio", "read", doc=portfolio_name, throw=True)
    if not frappe.db.exists("Bond Portfolio", portfolio_name):
        frappe.throw(_("Portfolio does not exist"))

    return {"from_date": from_date, "to_date": to_date, "portfolio_name": portfolio_name}


def get_data(filters: dict) -> list[dict]:
    query_filters = {}
    if filters["from_date"] and filters["to_date"]:
        query_filters["settlement_date"] = ["between", [filters["from_date"], filters["to_date"]]]
    elif filters["from_date"]:
        query_filters["settlement_date"] = [">=", filters["from_date"]]
    elif filters["to_date"]:
        query_filters["settlement_date"] = ["<=", filters["to_date"]]
    query_filters["portfolio_name"] = filters["portfolio_name"]

    rows = frappe.qb.get_query(
        "Bond Transaction",
        fields=[
            "transaction_reference",
            "settlement_date",
            "portfolio_name",
            "currency",
            "isin",
            "transaction_type",
            "accrued_interest_calculated",
            "accrued_interest_paid",
            "quantity_face_value",
            "face_value_per_unit",
            "coupon_rate",
            "coupon_frequency",
            "day_count_convention",
        ],
        filters=query_filters,
        order_by="portfolio_name asc, currency asc, settlement_date asc, transaction_reference asc",
        ignore_permissions=False,
    ).run(as_dict=True)
    for row in rows:
        calculated = Decimal(str(row.accrued_interest_calculated or 0))
        charged = Decimal(str(row.accrued_interest_paid or 0))
        row["accrued_interest_calculated"] = calculated
        row["accrued_interest_paid"] = charged
        row["interest_difference"] = (
            charged - calculated if row.transaction_type == "Sale" else calculated - charged
        )
    schedules = load_bond_schedules(rows)
    for row in rows:
        row["interest_difference_days"] = calculate_interest_difference_days(row, schedules.get(row.isin))
    return rows


def load_bond_schedules(rows: list[dict]) -> dict[str, dict]:
    isins = sorted({row.isin for row in rows})
    if not isins:
        return {}

    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=["name", "currency"],
        filters={"name": ["in", isins]},
        ignore_permissions=False,
    ).run(as_dict=True)
    schedules = {
        bond.name: {"currency": bond.currency, "coupon_schedule": [], "principal_schedule": []}
        for bond in bonds
    }
    readable_isins = list(schedules)
    for doctype, fieldname, fields, order_by in (
        (
            "Bond Coupon Schedule",
            "coupon_schedule",
            ["parent", "coupon_date", "period_start", "period_end", "coupon_factor"],
            "coupon_date asc",
        ),
        (
            "Bond Principal Schedule",
            "principal_schedule",
            ["parent", "repayment_date", "principal_units", "repayment_percent"],
            "repayment_date asc",
        ),
    ):
        if not readable_isins:
            break
        schedule_rows = frappe.qb.get_query(
            doctype,
            fields=fields,
            filters={
                "parent": ["in", readable_isins],
                "parenttype": "Bond Master",
                "parentfield": fieldname,
            },
            order_by=order_by,
            parent_doctype="Bond Master",
            ignore_permissions=False,
        ).run(as_dict=True)
        for row in schedule_rows:
            schedules[row.parent][fieldname].append(row)

    return schedules


def calculate_interest_difference_days(row: dict, schedules: dict | None) -> Decimal | None:
    if not schedules:
        return None

    bond = frappe._dict(
        {
            **schedules,
            "day_count_convention": row.day_count_convention,
            "face_value_per_unit": row.face_value_per_unit,
            "coupon_rate": row.coupon_rate,
            "coupon_frequency": row.coupon_frequency,
        }
    )
    settlement_date = getdate(row.settlement_date)
    period = get_coupon_period(bond.coupon_schedule, settlement_date)
    if not period:
        return None

    face_value = to_decimal(row.face_value_per_unit)
    coupon_rate = to_decimal(row.coupon_rate)
    quantity = to_decimal(row.quantity_face_value)
    convention = row.day_count_convention
    if is_kenya_day_count_convention(convention):
        period_days = (getdate(period.coupon_date) - getdate(period.period_start)).days
        if period_days <= 0:
            return None
        coupon_factor = to_decimal(
            period.coupon_factor
            if period.coupon_factor is not None
            else coupon_rate / to_decimal(row.coupon_frequency)
        )
        daily_per_unit = coupon_factor / Decimal(100) * face_value / to_decimal(period_days)
        quantity_factor = calculate_quantity_factor_from_bond(bond, settlement_date)
    else:
        daily_fraction = (
            Decimal(1) / Decimal(360)
            if convention == "30E/360"
            else year_fraction(
                convention,
                settlement_date - timedelta(days=1),
                settlement_date,
                row.coupon_frequency,
                reference_end_date=period.coupon_date,
            )
        )
        principal_factor = calculate_principal_factor_from_bond(bond, settlement_date)
        daily_per_unit = coupon_rate / Decimal(100) * face_value * daily_fraction * principal_factor
        quantity_factor = Decimal(1)

    daily_interest = daily_per_unit * quantity * quantity_factor
    if not daily_interest:
        return None
    return (row.interest_difference / daily_interest).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def make_total_rows(rows: list[dict]) -> list[dict]:
    totals: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.portfolio_name, row.currency)
        total = totals.setdefault(
            key,
            {
                "portfolio_name": row.portfolio_name,
                "currency": row.currency,
                "transaction_reference": _("Total"),
                "accrued_interest_calculated": Decimal("0"),
                "accrued_interest_paid": Decimal("0"),
                "interest_difference": Decimal("0"),
                "interest_difference_days": None,
                "is_total_row": 1,
            },
        )
        for field in ("accrued_interest_calculated", "accrued_interest_paid", "interest_difference"):
            total[field] += row[field]
    return list(totals.values())


def get_columns() -> list[dict]:
    return [
        {
            "label": _("Transaction Reference"),
            "fieldname": "transaction_reference",
            "fieldtype": "Data",
            "width": 170,
        },
        {"label": _("Settlement Date"), "fieldname": "settlement_date", "fieldtype": "Date", "width": 115},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 75},
        {
            "label": _("ISIN"),
            "fieldname": "isin",
            "fieldtype": "Link",
            "options": "Bond Master",
            "width": 160,
        },
        {"label": _("Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 90},
        {
            "label": _("Interest Calculated"),
            "fieldname": "accrued_interest_calculated",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 145,
        },
        {
            "label": _("Interest Charged"),
            "fieldname": "accrued_interest_paid",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 135,
        },
        {
            "label": _("Investor Gain + / Loss -"),
            "fieldname": "interest_difference",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 175,
        },
        {
            "label": _("Difference (Days, DCC)"),
            "fieldname": "interest_difference_days",
            "fieldtype": "Float",
            "precision": 2,
            "width": 135,
        },
    ]


def parse_date_filter(value, label: str) -> Date | None:
    value = optional_string(value, label)
    if not value:
        return None
    try:
        return getdate(value)
    except (TypeError, ValueError):
        frappe.throw(_("{0} must be a valid date").format(label))
