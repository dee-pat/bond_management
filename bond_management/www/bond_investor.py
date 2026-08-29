"""Website context for the feature-gated investor SPA."""

from typing import NoReturn
from urllib.parse import urlencode

import frappe

from bond_management.bond_management.utils.investor_ui import (
    get_investor_boot_context,
    is_investor_ui_enabled,
)

no_cache = 1


def get_context(context):
    """Serve the SPA only to an authenticated, explicitly allowed user."""
    if not is_investor_ui_enabled():
        _redirect_temporarily("/desk/bond-investor")

    if frappe.session.user == "Guest":
        request = getattr(frappe.local, "request", None)
        path = getattr(request, "path", "/bond-investor")
        _redirect_temporarily(f"/login?{urlencode({'redirect-to': path})}")

    context.update(
        {
            "boot": get_investor_boot_context(),
            "no_cache": 1,
            "title": "Bond Investor",
        }
    )
    return context


def _redirect_temporarily(location: str) -> NoReturn:
    """Redirect without letting browsers cache a rollout or session decision."""
    frappe.flags.redirect_location = location
    raise frappe.Redirect(http_status_code=302)
