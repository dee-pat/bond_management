"""Small runtime validators for values crossing whitelisted API and report boundaries."""

from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate


def required_string(value, label: str) -> str:
    """Return a non-empty string or raise a user-facing validation error."""
    if value is None:
        frappe.throw(_("{0} is required").format(label))
    if not isinstance(value, str):
        frappe.throw(_("{0} must be a string").format(label))
    if not value.strip():
        frappe.throw(_("{0} is required").format(label))
    return value


def optional_string(value, label: str) -> str | None:
    """Return an optional string, rejecting lists and other complex values."""
    if value is None:
        return None
    if not isinstance(value, str):
        frappe.throw(_("{0} must be a string").format(label))
    return value if value.strip() else None


def optional_date(value, label: str) -> date | None:
    """Return an optional date, rejecting non-strings and unparseable values."""
    value = optional_string(value, label)
    if not value:
        return None
    try:
        return getdate(value)
    except (TypeError, ValueError):
        frappe.throw(_("{0} must be a valid date").format(label))


def date_range_filter(from_date: date | None, to_date: date | None) -> list | None:
    """Return a query filter for an inclusive, optionally open-ended date range."""
    if from_date and to_date:
        return ["between", [from_date, to_date]]
    if from_date:
        return [">=", from_date]
    if to_date:
        return ["<=", to_date]
    return None
