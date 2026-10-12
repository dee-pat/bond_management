"""Small runtime validators for values crossing whitelisted API boundaries."""

import frappe
from frappe import _


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
