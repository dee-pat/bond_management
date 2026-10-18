# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from bond_management.bond_management.utils.validation import date_range_filter, optional_date


def execute(filters: dict | str | list | None = None) -> tuple[list[dict], list[dict]]:
    """Return persisted market yields, as percents, for the selected readable bonds and date range."""
    filters = validate_filters(filters)
    return get_columns(), get_data(filters)


def validate_filters(filters: dict | str | list | None) -> dict:
    """Normalize report filters; also accepts a JSON string, ``None`` or ``[]`` from the report runner."""
    if filters is None or filters == []:
        return {}
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    if not isinstance(filters, dict):
        frappe.throw(_("Report filters must be an object"))

    from_date = optional_date(filters.get("from_date"), "From Date")
    to_date = optional_date(filters.get("to_date"), "To Date")
    if from_date and to_date and from_date > to_date:
        frappe.throw(_("From Date must be on or before To Date"))

    return {
        "bonds": parse_bond_filter(filters.get("bonds")),
        "from_date": from_date,
        "to_date": to_date,
    }


def get_data(filters: dict) -> list[dict]:
    """Return permission-scoped market rows; ``future_xirr`` is ``None`` where the solver had no result."""
    readable_isins = get_readable_isins(filters["bonds"])
    if not readable_isins:
        return []

    market_filters = {"bond_market_prices.isin": ["in", readable_isins]}
    if dates := date_range_filter(filters["from_date"], filters["to_date"]):
        market_filters["date"] = dates

    rows = frappe.qb.get_query(
        "Bond Market Date",
        fields=[
            "date",
            "bond_market_prices.isin as isin",
            "bond_market_prices.currency as currency",
            "bond_market_prices.market_price as market_price",
            "bond_market_prices.future_xirr as future_xirr",
            "bond_market_prices.future_xirr_available as future_xirr_available",
        ],
        filters=market_filters,
        order_by="date asc, bond_market_prices.isin asc",
        ignore_permissions=False,
    ).run(as_dict=True)
    for row in rows:
        if not row.pop("future_xirr_available"):
            row.future_xirr = None
    return rows


def get_readable_isins(selected_isins: list[str] | None) -> list[str]:
    """Return readable bonds, or raise ``PermissionError`` when any selected bond is unreadable."""
    filters = {"name": ["in", selected_isins]} if selected_isins else None
    readable_isins = frappe.qb.get_query(
        "Bond Master",
        fields=["name"],
        filters=filters,
        order_by="name asc",
        ignore_permissions=False,
    ).run(pluck=True)

    if selected_isins and set(readable_isins) != set(selected_isins):
        frappe.throw(_("One or more selected bonds are not readable"), frappe.PermissionError)

    return readable_isins


def get_columns() -> list[dict]:
    """Return the report's column definitions."""
    return [
        {
            "label": _("Date"),
            "fieldname": "date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("ISIN"),
            "fieldname": "isin",
            "fieldtype": "Link",
            "options": "Bond Master",
            "width": 170,
        },
        {"label": _("CCY"), "fieldname": "currency", "width": 65},
        {
            "label": _("Market Price"),
            "fieldname": "market_price",
            "fieldtype": "Float",
            "width": 115,
        },
        {
            "label": _("Future XIRR"),
            "fieldname": "future_xirr",
            "fieldtype": "Percent",
            "width": 110,
        },
    ]


def parse_bond_filter(value: object) -> list[str] | None:
    """Return sorted, unique ISINs from a list or JSON list string; ``None`` when empty."""
    if value in (None, "", []):
        return None
    if isinstance(value, str):
        try:
            value = frappe.parse_json(value)
        except (TypeError, ValueError):
            frappe.throw(_("Bonds must be a list"))
    if not isinstance(value, list):
        frappe.throw(_("Bonds must be a list"))

    bonds = []
    for bond in value:
        if not isinstance(bond, str) or not bond.strip():
            frappe.throw(_("Every selected bond must be a non-empty string"))
        bonds.append(bond.strip())

    return sorted(set(bonds)) or None
