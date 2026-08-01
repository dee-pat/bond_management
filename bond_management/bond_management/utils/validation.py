"""Small runtime validators for values crossing whitelisted API boundaries."""

import frappe


def required_string(value, label: str) -> str:
    """Return a non-empty string or raise a user-facing validation error."""
    if value is None:
        frappe.throw(f"{label} is required")
    if not isinstance(value, str):
        frappe.throw(f"{label} must be a string")
    if not value.strip():
        frappe.throw(f"{label} is required")
    return value


def optional_string(value, label: str) -> str | None:
    """Return an optional string, rejecting lists and other complex values."""
    if value is None:
        return None
    if not isinstance(value, str):
        frappe.throw(f"{label} must be a string")
    return value if value.strip() else None
