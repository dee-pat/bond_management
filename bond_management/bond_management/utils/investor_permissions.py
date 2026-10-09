"""Portfolio isolation for users with the investor read-only role.

The assigned Bond Portfolio values are maintained with Frappe User Permission
records, so onboarding another investor only requires assigning the role and
their portfolio values. These hooks make that boundary explicit for list,
report, and direct-document access.
"""

import frappe
from frappe import _

INVESTOR_ROLE = "Bond Investor Read Only"
BOND_MANAGER_ROLE = "Bond Management Manager"
_ALLOWED_PERMISSION_TYPES = {"read", "report", "print", "email", "select"}


def has_investor_desk_access() -> bool:
    """Allow investors and managers to use the dedicated Bond Management Desk route."""
    roles = frappe.get_roles()
    return frappe.session.user == "Administrator" or BOND_MANAGER_ROLE in roles or INVESTOR_ROLE in roles


def redirect_investor_to_workspace(login_manager) -> None:
    """Start investor sessions at the Vue application, with Desk as its fallback."""
    if INVESTOR_ROLE not in frappe.get_roles(login_manager.user):
        return

    frappe.local.response["home_page"] = "/bond-investor"
    frappe.local.response.pop("redirect_to", None)


def is_investor_user(user: str, *, for_update: bool = False) -> bool:
    if not user or user in {"Administrator", "Guest"}:
        return False
    # This administrative role lookup owns the investor authorization boundary.
    # User role caches can be repopulated before a concurrent role save commits.
    return bool(
        frappe.qb.get_query(
            "Has Role",
            fields=["name"],
            filters={"parenttype": "User", "parent": user, "role": INVESTOR_ROLE},
            ignore_permissions=True,
            for_update=for_update,
        ).run(pluck=True)
    )


def _get_allowed_portfolios(user: str) -> list[str] | None:
    """Return assigned portfolios, or None when the user is not an investor."""
    if not is_investor_user(user):
        return None

    # User Permission is the administrative boundary for investor portfolios.
    # This service lookup must bypass the investor's lack of access to User
    # Permission records themselves.
    return frappe.qb.get_query(
        "User Permission",
        fields=["for_value"],
        filters={
            "user": user,
            "allow": "Bond Portfolio",
            "apply_to_all_doctypes": 1,
        },
        ignore_permissions=True,
    ).run(pluck=True)


def _portfolio_condition(doctype: str, fieldname: str, user: str) -> str | None:
    """Return Frappe's required permission-query SQL condition safely."""
    portfolios = _get_allowed_portfolios(user)
    if portfolios is None:
        return None
    _reject_incompatible_shared_documents(doctype, fieldname, user, portfolios)
    if not portfolios:
        return "1=0"

    # Frappe's permission-query hook requires a SQL condition string. The
    # identifiers are fixed by these internal callers; only database-escaped
    # User Permission values enter the condition.
    values = ", ".join(frappe.db.escape(portfolio) for portfolio in portfolios)
    return f"`tab{doctype}`.`{fieldname}` in ({values})"


def _reject_incompatible_shared_documents(doctype, fieldname, user, portfolios):
    """Fail closed if a legacy share would be ORed around the query condition."""
    shared_names = frappe.share.get_shared(doctype, user)
    if not shared_names:
        return

    shared_documents = frappe.qb.get_query(
        doctype,
        fields=["name", fieldname],
        filters={"name": ["in", shared_names]},
        ignore_permissions=True,
    ).run(as_dict=True)
    if any(document.get(fieldname) not in portfolios for document in shared_documents):
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def portfolio_query_condition(user: str) -> str | None:
    return _portfolio_condition("Bond Portfolio", "name", user)


def transaction_query_condition(user: str) -> str | None:
    return _portfolio_condition("Bond Transaction", "portfolio_name", user)


def statement_query_condition(user: str) -> str | None:
    return _portfolio_condition("Bond Statement", "portfolio_name", user)


def _has_portfolio_access(portfolio: str | None, user: str, ptype: str) -> bool | None:
    portfolios = _get_allowed_portfolios(user)
    if portfolios is None:
        # Frappe's controller permission hooks are deny-capable: a falsey
        # result denies access. Explicitly allow users outside the investor
        # boundary so their normal DocPerm role permissions remain effective.
        return True

    if ptype not in _ALLOWED_PERMISSION_TYPES or not portfolio or portfolio not in portfolios:
        # frappe.permissions.has_permission falls back to DocShare after a
        # false controller result. Raising here keeps a stale share from
        # overriding the investor's portfolio boundary.
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    return True


def investor_portfolio_access(user: str, portfolio: str) -> bool | None:
    """Return the investor assignment decision, or None for other users."""
    portfolios = _get_allowed_portfolios(user)
    if portfolios is None:
        return None
    return bool(portfolio and portfolio in portfolios)


def has_portfolio_permission(doc, user: str | None = None, ptype: str | None = None, **_kwargs):
    return _has_portfolio_access(doc.name, user, ptype)


def has_transaction_permission(doc, user: str | None = None, ptype: str | None = None, **_kwargs):
    return _has_portfolio_access(doc.portfolio_name, user, ptype)


def has_statement_permission(doc, user: str | None = None, ptype: str | None = None, **_kwargs):
    return _has_portfolio_access(doc.portfolio_name, user, ptype)
