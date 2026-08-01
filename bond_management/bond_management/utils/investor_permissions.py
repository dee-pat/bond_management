"""Portfolio isolation for users with the investor read-only role.

The assigned Bond Portfolio values are maintained with Frappe User Permission
records, so onboarding another investor only requires assigning the role and
their portfolio values. These hooks make that boundary explicit for list,
report, and direct-document access.
"""

import frappe

INVESTOR_ROLE = "Bond Investor Read Only"
_ALLOWED_PERMISSION_TYPES = {"read", "report", "print", "email"}


def has_investor_desk_access() -> bool:
    """Allow investors and Administrator to use the dedicated investor Desk route."""
    return frappe.session.user == "Administrator" or INVESTOR_ROLE in frappe.get_roles()


def redirect_investor_to_workspace(login_manager) -> None:
    """Start investor sessions at their restricted Workspace, not generic Desk."""
    if INVESTOR_ROLE not in frappe.get_roles(login_manager.user):
        return

    frappe.local.response["home_page"] = "/desk/bond-investor"
    frappe.local.response.pop("redirect_to", None)


def _get_allowed_portfolios(user: str) -> list[str] | None:
    """Return assigned portfolios, or None when the user is not an investor."""
    if user == "Administrator":
        return None

    if INVESTOR_ROLE not in frappe.get_roles(user):
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
    portfolios = _get_allowed_portfolios(user)
    if portfolios is None:
        return None
    if not portfolios:
        return "1=0"

    values = ", ".join(frappe.db.escape(portfolio) for portfolio in portfolios)
    return f"`tab{doctype}`.`{fieldname}` in ({values})"


def portfolio_query_condition(user: str) -> str | None:
    return _portfolio_condition("Bond Portfolio", "name", user)


def transaction_query_condition(user: str) -> str | None:
    return _portfolio_condition("Bond Transaction", "portfolio_name", user)


def statement_query_condition(user: str) -> str | None:
    return _portfolio_condition("Bond Statement", "portfolio_name", user)


def _has_portfolio_access(portfolio: str | None, user: str, ptype: str) -> bool | None:
    if ptype not in _ALLOWED_PERMISSION_TYPES:
        return None

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
