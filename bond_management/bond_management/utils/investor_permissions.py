"""Portfolio isolation for users with the investor read-only role.

The assigned Bond Portfolio values are maintained with Frappe User Permission
records, so onboarding another investor only requires assigning the role and
their portfolio values. These hooks make that boundary explicit for list,
report, and direct-document access.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import frappe
from frappe import _

INVESTOR_ROLE = "Bond Investor Read Only"
BOND_MANAGER_ROLE = "Bond Management Manager"
READ_PERMISSION_TYPES = {"read", "report", "print", "email", "select"}
PORTFOLIO_DOCTYPES = {
    "Bond Portfolio": "name",
    "Bond Transaction": "portfolio_name",
    "Bond Statement": "portfolio_name",
}


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


# Per-transaction caches live in ``frappe.db.value_cache``. Frappe clears it on
# commit, rollback (including savepoints), and for a DocType whenever one of its
# documents is saved or deleted. Roles are saved through User; assignments are
# User Permission documents. Locking reads always bypass the cache.
_INVESTOR_ROLE_CACHE_KEY = "__bond_investor_role__"
_ALLOWED_PORTFOLIOS_CACHE_KEY = "__bond_allowed_portfolios__"


def is_investor_user(user: str, *, for_update: bool = False) -> bool:
    if not user or user in {"Administrator", "Guest"}:
        return False
    cache = frappe.db.value_cache["User"][_INVESTOR_ROLE_CACHE_KEY]
    if not for_update and user in cache:
        return cache[user]
    # This administrative role lookup owns the investor authorization boundary.
    # User role caches can be repopulated before a concurrent role save commits.
    is_investor = bool(
        frappe.qb.get_query(
            "Has Role",
            fields=["name"],
            filters={"parenttype": "User", "parent": user, "role": INVESTOR_ROLE},
            ignore_permissions=True,
            for_update=for_update,
        ).run(pluck=True)
    )
    cache[user] = is_investor
    return is_investor


def get_allowed_portfolios(user: str) -> list[str] | None:
    """Return assigned portfolios, or None when the user is not an investor."""
    if not is_investor_user(user):
        return None

    cache = frappe.db.value_cache["User Permission"][_ALLOWED_PORTFOLIOS_CACHE_KEY]
    if user not in cache:
        # User Permission is the administrative boundary for investor portfolios.
        # This service lookup must bypass the investor's lack of access to User
        # Permission records themselves.
        cache[user] = tuple(
            frappe.qb.get_query(
                "User Permission",
                fields=["for_value"],
                filters={
                    "user": user,
                    "allow": "Bond Portfolio",
                    "apply_to_all_doctypes": 1,
                },
                ignore_permissions=True,
            ).run(pluck=True)
        )
    # Callers may mutate the list; never hand out the cached value.
    return list(cache[user])


def _portfolio_condition(doctype: str, fieldname: str, user: str) -> str | None:
    """Return Frappe's required permission-query SQL condition safely."""
    portfolios = get_allowed_portfolios(user)
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

    # Fail-closed boundary check: inspect every shared row, including rows
    # outside the caller's portfolio scope.
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


def file_query_condition(user: str | None = None) -> str | None:
    """Scope investor-visible private attachment metadata to assigned portfolios."""
    user = user or frappe.session.user
    portfolios = get_allowed_portfolios(user)
    if portfolios is None:
        return None
    _reject_out_of_scope_file_shares(user)

    portfolio_values = ", ".join(frappe.db.escape(portfolio) for portfolio in portfolios)
    scoped_doctypes = ", ".join(frappe.db.escape(doctype) for doctype in PORTFOLIO_DOCTYPES)
    file_owner = frappe.db.escape(user)
    # Ownership and shares never widen access to portfolio-scoped attachments.
    outside_portfolio_scope = f"COALESCE(`tabFile`.`attached_to_doctype`, '') NOT IN ({scoped_doctypes})"
    shared_file = (
        "EXISTS (SELECT 1 FROM `tabDocShare` "
        "WHERE `tabDocShare`.`share_doctype` = 'File' "
        "AND `tabDocShare`.`share_name` = `tabFile`.`name` "
        f"AND (`tabDocShare`.`user` = {file_owner} OR `tabDocShare`.`everyone` = 1) "
        "AND `tabDocShare`.`read` = 1)"
    )
    visible_portfolio = "1=0"
    if portfolios:
        visible_portfolio = (
            "(`tabFile`.`attached_to_doctype` = 'Bond Portfolio' "
            f"AND `tabFile`.`attached_to_name` IN ({portfolio_values})) OR "
            "(`tabFile`.`attached_to_doctype` = 'Bond Statement' AND EXISTS ("
            "SELECT 1 FROM `tabBond Statement` "
            "WHERE `tabBond Statement`.`name` = `tabFile`.`attached_to_name` "
            f"AND `tabBond Statement`.`portfolio_name` IN ({portfolio_values}))) OR "
            "(`tabFile`.`attached_to_doctype` = 'Bond Transaction' AND EXISTS ("
            "SELECT 1 FROM `tabBond Transaction` "
            "WHERE `tabBond Transaction`.`name` = `tabFile`.`attached_to_name` "
            f"AND `tabBond Transaction`.`portfolio_name` IN ({portfolio_values})))"
        )

    return (
        "(`tabFile`.`is_private` = 0 "
        f"OR ({outside_portfolio_scope} AND (`tabFile`.`owner` = {file_owner} OR {shared_file})) "
        f"OR ({visible_portfolio}))"
    )


def has_file_permission(doc, user: str | None = None, ptype: str | None = None, **_kwargs):
    if not is_file_in_investor_scope(doc, user or frappe.session.user, ptype):
        # Core File permission grants a direct share before this hook can
        # matter, so a false result would not deny access.
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    return True


def is_file_in_investor_scope(file, user: str, ptype: str | None = "read") -> bool:
    """Return False when an investor reaches beyond a read of an assigned portfolio's attachment."""
    portfolios = get_allowed_portfolios(user)
    if portfolios is None or not file.is_private:
        return True
    field = PORTFOLIO_DOCTYPES.get(file.attached_to_doctype)
    if not field:
        return True
    # Shares cannot make investors writers: they are read-only, as for portfolio documents.
    return ptype in READ_PERMISSION_TYPES and _attached_portfolio(file, field) in portfolios


class InvestorFileMixin:
    def is_downloadable(self):
        # Private downloads call core File permission directly, not app hooks.
        return super().is_downloadable() and is_file_in_investor_scope(self, frappe.session.user)


def _reject_out_of_scope_file_shares(user):
    """Fail closed: Frappe ORs shared names around the File query condition."""
    shared_names = frappe.share.get_shared("File", user)
    if not shared_names:
        return
    # This boundary inspects shared files before the caller's scope applies.
    shared_files = frappe.qb.get_query(
        "File",
        fields=["name", "is_private", "attached_to_doctype", "attached_to_name"],
        filters={"name": ["in", shared_names]},
        ignore_permissions=True,
    ).run(as_dict=True)
    if not all(is_file_in_investor_scope(file, user) for file in shared_files):
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _attached_portfolio(file, field):
    if not file.attached_to_name:
        return None
    if field == "name":
        return file.attached_to_name
    # This boundary must read the portfolio of a document the caller may not see.
    return frappe.db.get_value(file.attached_to_doctype, file.attached_to_name, field)


def exchange_rate_source_query_condition(user: str | None = None) -> str | None:
    """Limit provenance lists to explicitly shared rows in assigned portfolios."""
    user = user or frappe.session.user
    portfolios = get_allowed_portfolios(user)
    if portfolios is None:
        return None

    shared_names = _reject_incompatible_exchange_rate_source_shares(user, portfolios)
    if not portfolios or not shared_names:
        return "1=0"

    values = ", ".join(frappe.db.escape(portfolio) for portfolio in portfolios)
    return (
        "`tabBond Exchange Rate Source`.`name` in ("
        "select `tabDocShare`.`share_name` from `tabDocShare` "
        f"where `tabDocShare`.`share_doctype` = {frappe.db.escape('Bond Exchange Rate Source')} "
        f"and `tabDocShare`.`user` = {frappe.db.escape(user)} "
        "and `tabDocShare`.`read` = 1 and `tabDocShare`.`everyone` = 0) "
        "and `tabBond Exchange Rate Source`.`statement` in ("
        "select `tabBond Statement`.`name` from `tabBond Statement` "
        f"where `tabBond Statement`.`portfolio_name` in ({values}))"
    )


def has_exchange_rate_source_permission(doc, user=None, ptype=None, **_kwargs):
    user = user or frappe.session.user
    portfolios = get_allowed_portfolios(user)
    if portfolios is None:
        return True

    portfolio = get_statement_portfolio(doc.get("statement"))
    if (
        ptype not in READ_PERMISSION_TYPES
        or not portfolio
        or portfolio not in portfolios
        or not has_explicit_exchange_rate_source_share(user, doc.name)
    ):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    return True


def _reject_incompatible_exchange_rate_source_shares(user, portfolios):
    """Prevent DocShare's list-query OR from bypassing provenance scope."""
    shared_names = frappe.share.get_shared("Bond Exchange Rate Source", user, rights=["read"])
    if not shared_names:
        return []

    everyone_names = frappe.share.get_shared(
        "Bond Exchange Rate Source",
        user,
        rights=["read"],
        filters=[["everyone", "=", 1]],
    )
    if everyone_names:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    # This permission service must inspect the linked statement even when the
    # caller has no direct permission to read provenance or statement records.
    sources = frappe.qb.get_query(
        "Bond Exchange Rate Source",
        fields=["name", "statement"],
        filters={"name": ["in", shared_names]},
        ignore_permissions=True,
    ).run(as_dict=True)
    statement_names = {source.statement for source in sources if source.statement}
    statements = []
    if statement_names:
        statements = frappe.qb.get_query(
            "Bond Statement",
            fields=["name", "portfolio_name"],
            filters={"name": ["in", list(statement_names)]},
            ignore_permissions=True,
        ).run(as_dict=True)
    portfolio_by_statement = {statement.name: statement.portfolio_name for statement in statements}

    if any(portfolio_by_statement.get(source.statement) not in portfolios for source in sources):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    return shared_names


def has_explicit_exchange_rate_source_share(user, source_name):
    if not source_name:
        return False
    return bool(
        frappe.share.get_shared(
            "Bond Exchange Rate Source",
            user,
            rights=["read"],
            filters=[["share_name", "=", source_name], ["everyone", "=", 0]],
            limit=1,
        )
    )


def get_statement_portfolio(statement_name, *, for_update=False, wait=True):
    if not statement_name:
        return None
    return frappe.db.get_value(
        "Bond Statement",
        statement_name,
        "portfolio_name",
        for_update=for_update,
        wait=wait,
    )


_SHARED_EXCHANGE_RATE_PROJECTION_FLAG = "include_shared_exchange_rates_in_safe_projection"


@contextmanager
def include_shared_exchange_rates_in_safe_projection() -> Iterator[None]:
    """Keep shared rate history visible to a fixed projection without exposing its private link."""
    flag_was_set = _SHARED_EXCHANGE_RATE_PROJECTION_FLAG in frappe.flags
    previous_value = frappe.flags.get(_SHARED_EXCHANGE_RATE_PROJECTION_FLAG)
    frappe.flags[_SHARED_EXCHANGE_RATE_PROJECTION_FLAG] = True
    try:
        yield
    finally:
        if flag_was_set:
            frappe.flags[_SHARED_EXCHANGE_RATE_PROJECTION_FLAG] = previous_value
        else:
            frappe.flags.pop(_SHARED_EXCHANGE_RATE_PROJECTION_FLAG, None)


def exchange_rate_query_condition(user: str | None = None) -> str | None:
    """Hide rows linked to statements the caller cannot read, including filter probes."""
    if frappe.flags.get(_SHARED_EXCHANGE_RATE_PROJECTION_FLAG):
        return None

    user = user or frappe.session.user
    statement_condition = statement_query_condition(user)
    if statement_condition is None:
        return None

    # Keep the privacy boundary at query level too, so generic list paths that
    # accept a protected-field filter cannot use an unreadable link as an oracle.
    return (
        "(`tabBond Exchange Rate`.`statement` is null or "
        "`tabBond Exchange Rate`.`statement` in ("
        "select `tabBond Statement`.`name` from `tabBond Statement` "
        f"where {statement_condition}))"
    )


def _has_portfolio_access(portfolio: str | None, user: str, ptype: str) -> bool | None:
    portfolios = get_allowed_portfolios(user)
    if portfolios is None:
        # Frappe's controller permission hooks are deny-capable: a falsey
        # result denies access. Explicitly allow users outside the investor
        # boundary so their normal DocPerm role permissions remain effective.
        return True

    if ptype not in READ_PERMISSION_TYPES or not portfolio or portfolio not in portfolios:
        # frappe.permissions.has_permission falls back to DocShare after a
        # false controller result. Raising here keeps a stale share from
        # overriding the investor's portfolio boundary.
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    return True


def has_portfolio_permission(doc, user: str | None = None, ptype: str | None = None, **_kwargs):
    return _has_portfolio_access(doc.name, user, ptype)


def has_transaction_permission(doc, user: str | None = None, ptype: str | None = None, **_kwargs):
    return _has_portfolio_access(doc.portfolio_name, user, ptype)


def has_statement_permission(doc, user: str | None = None, ptype: str | None = None, **_kwargs):
    return _has_portfolio_access(doc.portfolio_name, user, ptype)
