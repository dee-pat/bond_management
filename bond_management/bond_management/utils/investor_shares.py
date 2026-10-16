"""Keep Frappe shares subordinate to the app's investor boundary."""

import frappe
from frappe import _

from bond_management.bond_management.utils.investor_permissions import (
    PORTFOLIO_DOCTYPES,
    READ_PERMISSION_TYPES,
    get_allowed_portfolios,
    get_statement_portfolio,
    has_explicit_exchange_rate_source_share,
    is_investor_user,
)

SOURCE_DOCTYPE = "Bond Exchange Rate Source"
FINANCIAL_DOCTYPES = (
    *PORTFOLIO_DOCTYPES,
    "Bond Master",
    "Bond Market Date",
    "Bond Exchange Rate",
    SOURCE_DOCTYPE,
)
MUTATING_SHARE_FIELDS = ("write", "submit", "share")
_FILE_FIELDS = ["name", "is_private", "attached_to_doctype", "attached_to_name"]
_DEFERRED_SHARE_TARGET = object()


class InvestorBoundaryMixin:
    def has_permission(self, permtype="read", *, debug=False, user=None):
        user = user or frappe.session.user
        if not _investor_document_access(self, user, permtype):
            return False
        return super().has_permission(permtype, debug=debug, user=user)


def reject_investor_mutation(doc, method=None):
    user = frappe.session.user
    if user in {"Administrator", "Guest"}:
        return
    recipients = []
    if not doc.is_new():
        _lock_share_target(doc.doctype, doc.name)
        if doc.doctype in PORTFOLIO_DOCTYPES or doc.doctype == SOURCE_DOCTYPE:
            recipients = frappe.qb.get_query(
                "DocShare",
                fields=["user"],
                filters={"share_doctype": doc.doctype, "share_name": doc.name},
                ignore_permissions=True,
                for_update=True,
            ).run(pluck=True)
    # The target lock prevents new shares; the locking read sees late commits.
    _lock_users([user, *recipients])
    if is_investor_user(user, for_update=True):
        _deny()


def reject_investor_share_mutation(doc, method=None):
    if doc.share_doctype not in FINANCIAL_DOCTYPES:
        return
    user = frappe.session.user
    if user in {"Administrator", "Guest"}:
        return
    # delete_doc locks DocShare before on_trash, so this check must not wait on
    # User: cleanup and share saves acquire User before the DocShare row.
    if is_investor_user(user):
        _deny()


def validate_share(doc, method, share):
    # Document hooks receive (target, event_name, DocShare). Core may have loaded
    # the target earlier; re-read its current portfolio under its primary-key lock.
    target = _lock_share_target(doc.doctype, doc.name)
    _lock_users([frappe.session.user, share.user])
    _validate_locked_share(target, share)


def validate_file_share(doc, method, share):
    # Match document saves: target, users, then File. A save locks its users
    # before File rows matched by URL, which may be attached elsewhere.
    seen = frappe.db.get_value("File", doc.name, _FILE_FIELDS, as_dict=True)
    target = _lock_attachment_target(seen)
    _lock_users([frappe.session.user, share.user])
    file = _lock_file(doc.name)
    if _scoped_attachment(file) != _scoped_attachment(seen):
        # Relinked or made private after the first read. Waiting for the new
        # target while holding users and File would invert the order.
        target = _lock_attachment_target(file, wait=False)
    if not _scoped_attachment(file):
        return
    if is_investor_user(frappe.session.user, for_update=True):
        _deny()
    if _restricted_recipient(share) and any(share.get(field) for field in MUTATING_SHARE_FIELDS):
        _deny()
    if _inaccessible_file_share(file, target, share):
        _deny()


def cleanup_file_shares(doc, method=None):
    """Drop shares made stale when a shared File is made private or relinked."""
    if not doc.get_doc_before_save():
        return
    if not any(
        doc.has_value_changed(field) for field in ("is_private", "attached_to_doctype", "attached_to_name")
    ):
        return
    try:
        # This save holds the File; waiting for recipients would invert the order.
        cleanup_incompatible_file_shares(file=doc.name, wait=False)
    except frappe.QueryTimeoutError:
        frappe.enqueue(cleanup_incompatible_file_shares, file=doc.name, enqueue_after_commit=True)


def cleanup_incompatible_file_shares(user=None, doctype=None, name=None, file=None, *, wait=True):
    """Remove File shares that portfolio scope no longer allows.

    A stale share would make the recipient's File list fail closed. Like
    cleanup_incompatible_shares, this administrative repair reads rows the
    caller cannot see and leaves the transaction to the caller. A caller that
    passes ``user`` already holds that user's lock.
    """
    filters = {"share_doctype": "File"}
    if user:
        filters["user"] = user
    if doctype:
        attached_files = frappe.qb.get_query(
            "File",
            fields=["name"],
            filters={"attached_to_doctype": doctype, "attached_to_name": name},
            ignore_permissions=True,
        ).run(pluck=True)
        if not attached_files:
            return
        filters["share_name"] = ["in", attached_files]
    if file:
        filters["share_name"] = file

    if not user:
        _lock_users(
            frappe.qb.get_query("DocShare", fields=["user"], filters=filters, ignore_permissions=True).run(
                pluck=True
            ),
            wait=wait,
        )
    shares = frappe.qb.get_query(
        "DocShare", fields=["*"], filters=filters, ignore_permissions=True, for_update=True
    ).run(as_dict=True)
    if not shares:
        return
    locked = {name: _lock_unseen_file(name) for name in sorted({share.share_name for share in shares})}
    for share in shares:
        file, target = locked[share.share_name]
        if file is _DEFERRED_SHARE_TARGET or not _scoped_attachment(file):
            continue
        if _inaccessible_file_share(file, target, share):
            frappe.delete_doc(
                "DocShare", share.name, ignore_permissions=True, flags={"ignore_share_permission": True}
            )
        elif _restricted_recipient(share) and any(share.get(field) for field in MUTATING_SHARE_FIELDS):
            _drop_mutating_rights(share)


def cleanup_incompatible_shares(user=None, doctype=None, name=None, names=None):
    """Administrative invariant repair; the caller owns the request transaction.

    The service reads shares and assignment data without investor permissions
    because investors cannot administer either. Only this app's conflicting
    rows are changed, using DocShare's own delete API for cache/audit behavior.
    """
    filters = {"share_doctype": ["in", FINANCIAL_DOCTYPES]}
    if user:
        filters["user"] = user
    if doctype:
        filters["share_doctype"] = doctype
        if name:
            filters["share_name"] = name
        elif names is not None:
            if not names:
                return
            filters["share_name"] = ["in", names]
    targets = _lock_share_targets(filters)
    if user:
        _lock_users([user])
    else:
        recipients = frappe.qb.get_query(
            "DocShare", fields=["user"], filters=filters, ignore_permissions=True
        ).run(pluck=True)
        _lock_users(recipients)
    shares = frappe.qb.get_query(
        "DocShare", fields=["*"], filters=filters, ignore_permissions=True, for_update=True
    ).run(as_dict=True)
    for share in shares:
        key = (share.share_doctype, share.share_name)
        if key in targets:
            target = targets[key]
        else:
            target = _lock_unseen_share_target(*key)
        if target is _DEFERRED_SHARE_TARGET:
            continue
        if target is None:
            # DocShare.on_trash comments on its target; orphan rows have none.
            frappe.delete_doc("DocShare", share.name, ignore_permissions=True, ignore_on_trash=True)
            continue
        if _inaccessible_share(target, share):
            frappe.delete_doc(
                "DocShare", share.name, ignore_permissions=True, flags={"ignore_share_permission": True}
            )
        elif _restricted_recipient(share) and any(share.get(field) for field in MUTATING_SHARE_FIELDS):
            _drop_mutating_rights(share)

    if doctype is None or (doctype in PORTFOLIO_DOCTYPES and name):
        cleanup_incompatible_file_shares(user=user, doctype=doctype, name=name)


def lock_user_authorization(doc, method=None):
    _lock_user_share_targets([doc.name])
    _lock_users([doc.name])


def lock_assignment_authorization(doc, method=None):
    previous = doc.get_doc_before_save()
    users = [doc.user, previous.user if previous else None]
    _lock_user_share_targets(users)
    _lock_users(users)


def lock_share_authorization(doc, method=None):
    if doc.share_doctype in FINANCIAL_DOCTYPES:
        # Sharing and portfolio reassignment acquire target, then recipients.
        target = _lock_share_target(doc.share_doctype, doc.share_name)
        previous = doc.get_doc_before_save()
        _lock_users([frappe.session.user, doc.user, previous.user if previous else None])
        # before_validate still runs when a server caller sets ignore_validate.
        _validate_locked_share(target, doc)


@frappe.whitelist()
def clear_user_permissions(user: str, for_doctype: str):
    from frappe.core.doctype.user_permission.user_permission import (
        clear_user_permissions as clear_permissions,
    )

    if not isinstance(user, str) or not isinstance(for_doctype, str):
        frappe.throw(_("User and DocType must be strings."), frappe.ValidationError)
    frappe.only_for("System Manager")
    _lock_user_share_targets([user])
    _lock_users([user])
    result = clear_permissions(user, for_doctype)
    if for_doctype == "Bond Portfolio":
        cleanup_incompatible_shares(user=user)
    return result


def cleanup_user_shares(doc, method=None):
    if is_investor_user(doc.name, for_update=True):
        cleanup_incompatible_shares(user=doc.name)


def cleanup_assignment_shares(doc, method=None):
    previous = doc.get_doc_before_save()
    for user in sorted({doc.user, previous.user if previous else doc.user}):
        # Frappe clears only the current recipient's User Permission cache.
        frappe.cache.hdel("user_permissions", user)
        if is_investor_user(user, for_update=True):
            cleanup_incompatible_shares(user=user)


def cleanup_document_shares(doc, method=None):
    if doc.doctype not in PORTFOLIO_DOCTYPES:
        return

    cleanup_incompatible_shares(doctype=doc.doctype, name=doc.name)
    if doc.doctype != "Bond Statement":
        return

    previous = doc.get_doc_before_save()
    if previous and previous.portfolio_name != doc.portfolio_name:
        source_names = frappe.qb.get_query(
            SOURCE_DOCTYPE,
            fields=["name"],
            filters={"statement": doc.name},
            ignore_permissions=True,
        ).run(pluck=True)
        cleanup_incompatible_shares(doctype=SOURCE_DOCTYPE, names=source_names)


def _investor_document_access(doc, user, permtype):
    portfolios = get_allowed_portfolios(user)
    if portfolios is None:
        return True
    if permtype not in READ_PERMISSION_TYPES:
        return False
    field = PORTFOLIO_DOCTYPES.get(doc.doctype)
    if field:
        portfolio = doc.get(field)
    elif doc.doctype == SOURCE_DOCTYPE:
        portfolio = _document_portfolio(doc)
        return bool(
            portfolio and portfolio in portfolios and has_explicit_exchange_rate_source_share(user, doc.name)
        )
    else:
        return True
    return bool(portfolio and portfolio in portfolios)


def _lock_share_target(doctype, name, *, wait=True):
    if doctype == SOURCE_DOCTYPE:
        return _lock_exchange_rate_source_target(name, wait=wait)

    field = PORTFOLIO_DOCTYPES.get(doctype)
    current = frappe.db.get_value(doctype, name, field or "name", for_update=True, wait=wait)
    if current is None:
        return None

    target = frappe._dict(doctype=doctype, name=name)
    if field:
        target[field] = current
    return target


def _lock_exchange_rate_source_target(name, *, wait=True):
    statement_name = frappe.db.get_value(SOURCE_DOCTYPE, name, "statement")
    if not statement_name:
        return None

    # Statement saves lock their row before synchronizing provenance rows.
    # Keep the same parent-before-child order when validating a source share.
    portfolio = get_statement_portfolio(statement_name, for_update=True, wait=wait)
    if portfolio is None:
        return None

    return _lock_exchange_rate_source_row(name, statement_name, portfolio, wait=wait)


def _lock_exchange_rate_source_row(name, statement_name, portfolio, *, wait=True):
    if not statement_name or portfolio is None:
        return None

    current_statement = frappe.db.get_value(
        SOURCE_DOCTYPE,
        name,
        "statement",
        for_update=True,
        wait=wait,
    )
    if not current_statement:
        return None
    if current_statement != statement_name:
        frappe.throw(
            _("The statement for exchange-rate provenance changed while access was being checked."),
            frappe.ValidationError,
        )

    return frappe._dict(
        doctype=SOURCE_DOCTYPE,
        name=name,
        statement=statement_name,
        portfolio_name=portfolio,
    )


def _lock_unseen_share_target(doctype, name):
    try:
        return _lock_share_target(doctype, name, wait=False)
    except frappe.QueryTimeoutError:
        # A concurrent target save may hold this row while waiting for the
        # recipient User lock. A normal read can use an older snapshot and
        # mistake a newly committed target for an orphan, so retry after commit.
        # Deadlocks must escape so Frappe rolls back the whole request transaction.
        frappe.enqueue(
            cleanup_incompatible_shares,
            doctype=doctype,
            name=name,
            enqueue_after_commit=True,
        )
        return _DEFERRED_SHARE_TARGET


def _lock_share_targets(filters):
    references = frappe.qb.get_query(
        "DocShare",
        fields=["share_doctype", "share_name"],
        filters=filters,
        ignore_permissions=True,
    ).run(as_dict=True)
    keys = sorted({(share.share_doctype, share.share_name) for share in references})
    source_names = sorted(name for doctype, name in keys if doctype == SOURCE_DOCTYPE)
    source_links = {}
    if source_names:
        source_links = {
            source.name: source.statement
            for source in frappe.qb.get_query(
                SOURCE_DOCTYPE,
                fields=["name", "statement"],
                filters={"name": ["in", source_names]},
                ignore_permissions=True,
            ).run(as_dict=True)
        }

    statement_names = {name for doctype, name in keys if doctype == "Bond Statement"}
    statement_names.update(statement for statement in source_links.values() if statement)
    statement_portfolios = {
        statement_name: get_statement_portfolio(statement_name, for_update=True)
        for statement_name in sorted(statement_names)
    }

    targets = {}
    for doctype, name in keys:
        if doctype == "Bond Statement":
            portfolio = statement_portfolios[name]
            if portfolio is None:
                targets[(doctype, name)] = None
            else:
                target = frappe._dict(doctype=doctype, name=name)
                target[PORTFOLIO_DOCTYPES[doctype]] = portfolio
                targets[(doctype, name)] = target
        elif doctype != SOURCE_DOCTYPE:
            targets[(doctype, name)] = _lock_share_target(doctype, name)

    for name in source_names:
        statement_name = source_links.get(name)
        targets[(SOURCE_DOCTYPE, name)] = _lock_exchange_rate_source_row(
            name,
            statement_name,
            statement_portfolios.get(statement_name),
        )

    return targets


def _lock_user_share_targets(users):
    users = sorted({user for user in users if user})
    if not users:
        return
    _lock_share_targets(
        {
            "share_doctype": ["in", FINANCIAL_DOCTYPES],
            "user": ["in", users],
        }
    )


def _validate_locked_share(target, share):
    if target is None or is_investor_user(frappe.session.user, for_update=True):
        _deny()
    if _inaccessible_share(target, share):
        _deny()
    if _restricted_recipient(share) and any(share.get(field) for field in MUTATING_SHARE_FIELDS):
        _deny()


def _lock_file(name, *, wait=True):
    return frappe.db.get_value(
        "File",
        name,
        _FILE_FIELDS,
        as_dict=True,
        for_update=True,
        wait=wait,
    )


def _drop_mutating_rights(share):
    # Narrow administrative repair avoids target validation and retains the
    # original owner and read grant; DocShare has no derived fields.
    frappe.db.set_value(
        "DocShare", share.name, dict.fromkeys(MUTATING_SHARE_FIELDS, 0), update_modified=False
    )
    frappe.clear_document_cache("DocShare", share.name)


def _lock_attachment_target(file, *, wait=True):
    attachment = _scoped_attachment(file)
    return _lock_share_target(*attachment, wait=wait) if attachment else None


def _scoped_attachment(file):
    if not file or not _is_portfolio_attachment(file):
        return None
    return file.attached_to_doctype, file.attached_to_name


def _lock_unseen_file(name):
    """Read a File and its target currently without waiting behind held User locks.

    Cleanup holds recipients, which share validation locks before File. A
    plain read could miss a File committed after this transaction's snapshot.
    """
    try:
        file = _lock_file(name, wait=False)
        return file, _lock_attachment_target(file, wait=False)
    except frappe.QueryTimeoutError:
        frappe.enqueue(cleanup_incompatible_file_shares, file=name, enqueue_after_commit=True)
        return _DEFERRED_SHARE_TARGET, None


def _is_portfolio_attachment(file):
    return bool(file.is_private) and file.attached_to_doctype in PORTFOLIO_DOCTYPES


def _inaccessible_file_share(file, target, share):
    if not _is_portfolio_attachment(file):
        return False
    if share.everyone:
        return True
    portfolios = _recipient_portfolios(share.user)
    portfolio = target.get(PORTFOLIO_DOCTYPES[file.attached_to_doctype]) if target else None
    return portfolios is not None and portfolio not in portfolios


def _inaccessible_share(doc, share):
    if doc.doctype not in PORTFOLIO_DOCTYPES and doc.doctype != SOURCE_DOCTYPE:
        return False
    if share.everyone:
        return True
    portfolios = _recipient_portfolios(share.user)
    return portfolios is not None and _document_portfolio(doc) not in portfolios


def _document_portfolio(doc):
    field = PORTFOLIO_DOCTYPES.get(doc.doctype)
    if field:
        return doc.get(field)
    if doc.doctype == SOURCE_DOCTYPE:
        return doc.get("portfolio_name") or get_statement_portfolio(doc.get("statement"))
    return None


def _restricted_recipient(share):
    return bool(share.everyone or is_investor_user(share.user, for_update=True))


def _recipient_portfolios(user):
    if not is_investor_user(user, for_update=True):
        return None
    # Locking reads see committed changes after waiting for the recipient lock,
    # even when the request established an older repeatable-read snapshot.
    return frappe.qb.get_query(
        "User Permission",
        fields=["for_value"],
        filters={"user": user, "allow": "Bond Portfolio", "apply_to_all_doctypes": 1},
        ignore_permissions=True,
        for_update=True,
    ).run(pluck=True)


def _lock_users(users, *, wait=True):
    # The primary key is the common authorization lock for shares, roles, and
    # assignments. Sorted acquisition also covers assignment-recipient changes.
    for user in sorted({user for user in users if user}):
        frappe.db.get_value("User", user, "name", for_update=True, wait=wait)


def _deny():
    frappe.throw(_("Document sharing cannot override investor access restrictions."), frappe.PermissionError)
