"""Keep Frappe shares subordinate to the app's investor boundary."""

import frappe
from frappe import _

from bond_management.bond_management.utils.investor_permissions import (
    _get_allowed_portfolios,
    is_investor_user,
)

PORTFOLIO_DOCTYPES = {
    "Bond Portfolio": "name",
    "Bond Transaction": "portfolio_name",
    "Bond Statement": "portfolio_name",
}
FINANCIAL_DOCTYPES = (*PORTFOLIO_DOCTYPES, "Bond Master", "Bond Market Date", "Bond Exchange Rate")
READ_PERMISSION_TYPES = {"read", "report", "print", "email", "select"}
MUTATING_SHARE_FIELDS = ("write", "submit", "share")


class InvestorBoundaryMixin:
    def has_permission(self, permtype="read", *, debug=False, user=None):
        user = user or frappe.session.user
        if not _investor_document_access(self, user, permtype):
            return False
        return super().has_permission(permtype, debug=debug, user=user)


def reject_investor_mutation(doc, method=None):
    if is_investor_user(frappe.session.user):
        _deny()


def reject_investor_share_mutation(doc, method=None):
    if doc.share_doctype not in FINANCIAL_DOCTYPES:
        return
    user = frappe.session.user
    if user in {"Administrator", "Guest"}:
        return
    _lock_users([user])
    if is_investor_user(user, for_update=True):
        _deny()


def validate_share(doc, method, share):
    # Document hooks receive (target, event_name, DocShare). Core may have loaded
    # the target earlier; re-read its current portfolio under its primary-key lock.
    target = _lock_share_target(doc.doctype, doc.name)
    _lock_users([frappe.session.user, share.user])
    _validate_locked_share(target, share)


def cleanup_incompatible_shares(user=None, doctype=None, name=None):
    """Administrative invariant repair; the caller owns the request transaction.

    The service reads shares and assignment data without investor permissions
    because investors cannot administer either. Only this app's conflicting
    rows are changed, using DocShare's own delete API for cache/audit behavior.
    """
    filters = {"share_doctype": ["in", FINANCIAL_DOCTYPES]}
    if user:
        filters["user"] = user
    if doctype:
        filters.update(share_doctype=doctype, share_name=name)
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
        try:
            target = frappe.get_doc(share.share_doctype, share.share_name)
        except frappe.DoesNotExistError:
            # DocShare.on_trash comments on its target; orphan rows have none.
            frappe.delete_doc("DocShare", share.name, ignore_permissions=True, ignore_on_trash=True)
            continue
        if _inaccessible_share(target, share):
            frappe.delete_doc(
                "DocShare", share.name, ignore_permissions=True, flags={"ignore_share_permission": True}
            )
        elif _restricted_recipient(share) and any(share.get(field) for field in MUTATING_SHARE_FIELDS):
            # Narrow administrative repair avoids target validation and retains
            # the original owner and read grant; DocShare has no derived fields.
            frappe.db.set_value(
                "DocShare", share.name, dict.fromkeys(MUTATING_SHARE_FIELDS, 0), update_modified=False
            )
            frappe.clear_document_cache("DocShare", share.name)


def lock_user_authorization(doc, method=None):
    _lock_users([doc.name])


def lock_assignment_authorization(doc, method=None):
    previous = doc.get_doc_before_save()
    _lock_users([doc.user, previous.user if previous else None])


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
    if doc.doctype in PORTFOLIO_DOCTYPES:
        cleanup_incompatible_shares(doctype=doc.doctype, name=doc.name)


def _investor_document_access(doc, user, permtype):
    portfolios = _get_allowed_portfolios(user)
    if portfolios is None:
        return True
    if permtype not in READ_PERMISSION_TYPES:
        return False
    field = PORTFOLIO_DOCTYPES.get(doc.doctype)
    return field is None or doc.get(field) in portfolios


def _lock_share_target(doctype, name):
    field = PORTFOLIO_DOCTYPES.get(doctype)
    current = frappe.db.get_value(doctype, name, field or "name", for_update=True)
    target = frappe._dict(doctype=doctype)
    if field:
        target[field] = current
    return target


def _validate_locked_share(target, share):
    if is_investor_user(frappe.session.user, for_update=True):
        _deny()
    if _inaccessible_share(target, share):
        _deny()
    if _restricted_recipient(share) and any(share.get(field) for field in MUTATING_SHARE_FIELDS):
        _deny()


def _inaccessible_share(doc, share):
    field = PORTFOLIO_DOCTYPES.get(doc.doctype)
    if field is None:
        return False
    if share.everyone:
        return True
    portfolios = _recipient_portfolios(share.user)
    return portfolios is not None and doc.get(field) not in portfolios


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


def _lock_users(users):
    # The primary key is the common authorization lock for shares, roles, and
    # assignments. Sorted acquisition also covers assignment-recipient changes.
    for user in sorted({user for user in users if user}):
        frappe.db.get_value("User", user, "name", for_update=True)


def _deny():
    frappe.throw(_("Document sharing cannot override investor access restrictions."), frappe.PermissionError)
