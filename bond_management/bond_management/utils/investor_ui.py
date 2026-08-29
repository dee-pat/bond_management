"""Access and boot-context helpers for the investor web application."""

import frappe
from frappe import _
from frappe.sessions import get_csrf_token
from frappe.utils import cint, get_fullname

from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
    has_investor_desk_access,
)

FEATURE_FLAG = "bond_investor_spa_enabled"


def is_investor_ui_enabled() -> bool:
    """Return the site-level rollout state, disabled when no setting exists."""
    return bool(cint(frappe.conf.get(FEATURE_FLAG, 0)))


def require_investor_ui_access() -> None:
    """Enforce authentication, rollout, and role gates for investor APIs."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Login is required to access the investor application."), frappe.AuthenticationError)

    if not is_investor_ui_enabled():
        frappe.throw(_("The investor application is not enabled for this site."), frappe.PermissionError)

    if not has_investor_desk_access():
        frappe.throw(_("You are not permitted to access the investor application."), frappe.PermissionError)


def get_investor_boot_context() -> dict:
    """Return the minimum trusted context embedded in the SPA website entry."""
    require_investor_ui_access()

    user = frappe.session.user
    roles = set(frappe.get_roles(user))
    is_support_user = user == "Administrator" or BOND_MANAGER_ROLE in roles

    return {
        "csrf_token": get_csrf_token(),
        "bond_investor": {
            "feature_enabled": True,
            "user": {
                "name": user,
                "full_name": get_fullname(user),
            },
            "is_investor": INVESTOR_ROLE in roles,
            "is_support": is_support_user,
        },
    }
