"""Keep investors read-only and financial documents unshared (decision 0012)."""

from typing import NoReturn

import frappe
from frappe import _
from frappe.model.document import Document

from bond_management.bond_management.utils.investor_permissions import (
    FINANCIAL_DOCTYPES,
    PORTFOLIO_DOCTYPES,
    READ_PERMISSION_TYPES,
    SOURCE_DOCTYPE,
    get_allowed_portfolios,
    is_investor_user,
)


class InvestorBoundaryMixin:
    def has_permission(self, permtype: str = "read", *, debug: bool = False, user: str | None = None) -> bool:
        """Deny investors outside their portfolio scope before core DocPerm checks run."""
        user = user or frappe.session.user
        if not _investor_document_access(self, user, permtype):
            return False
        return super().has_permission(permtype, debug=debug, user=user)


def reject_investor_mutation(doc: Document, method: str | None = None) -> None:
    """Document hook: raise ``PermissionError`` when an investor writes a financial document."""
    if is_investor_user(frappe.session.user):
        _deny(_("Investors cannot change financial documents."))


def reject_financial_share(doc: Document, method: str | None = None) -> None:
    """DocShare hook: financial documents and their Files are never shared, even by Administrator."""
    # before_validate still runs when a server caller sets ignore_validate.
    if doc.share_doctype in FINANCIAL_DOCTYPES or (
        doc.share_doctype == "File" and _is_financial_file(doc.share_name)
    ):
        _deny(_("Financial documents and their attachments cannot be shared."))


def remove_financial_file_shares(doc: Document, method: str | None = None) -> None:
    """File hook: a File attached to a financial document keeps no shares."""
    if doc.attached_to_doctype in FINANCIAL_DOCTYPES:
        delete_financial_shares(file=doc.name)


def delete_financial_shares(file: str | None = None) -> None:
    """Delete shares of financial documents and of their Files, or of one such ``file``; safe to rerun.

    Share maintenance reads and removes every grant, whatever the caller can see.
    """
    if file:
        shares = _shares({"share_doctype": "File", "share_name": file})
    else:
        shares = _shares({"share_doctype": ["in", FINANCIAL_DOCTYPES]})
        file_shares = _shares({"share_doctype": "File"})
        financial_files = _financial_files({share.share_name for share in file_shares})
        shares += [share for share in file_shares if share.share_name in financial_files]
    for share in shares:
        frappe.delete_doc(
            "DocShare",
            share.name,
            ignore_permissions=True,
            # DocShare comments on its target; an orphan grant has none.
            ignore_on_trash=not frappe.db.exists(share.share_doctype, share.share_name),
            flags={"ignore_share_permission": True},
        )


def clear_previous_assignee_cache(doc: Document, method: str | None = None) -> None:
    """User Permission hook: Frappe clears only the new user's cache when an assignment moves."""
    previous = doc.get_doc_before_save()
    if previous and previous.user != doc.user:
        frappe.cache.hdel("user_permissions", previous.user)


def _investor_document_access(doc: Document, user: str, permtype: str) -> bool:
    portfolios = get_allowed_portfolios(user)
    if portfolios is None:
        return True
    if permtype not in READ_PERMISSION_TYPES or doc.doctype == SOURCE_DOCTYPE:
        return False
    field = PORTFOLIO_DOCTYPES.get(doc.doctype)
    return not field or bool(doc.get(field) and doc.get(field) in portfolios)


def _is_financial_file(name: str) -> bool:
    # Locking the File orders this check with a concurrent relink: either this
    # check sees the new attachment, or the relink's save removes this share.
    attached_to = frappe.db.get_value("File", name, "attached_to_doctype", for_update=True)
    return attached_to in FINANCIAL_DOCTYPES


def _financial_files(names: set[str]) -> set[str]:
    if not names:
        return set()
    return set(
        frappe.qb.get_query(
            "File",
            fields=["name"],
            filters={"name": ["in", list(names)], "attached_to_doctype": ["in", FINANCIAL_DOCTYPES]},
            ignore_permissions=True,
        ).run(pluck=True)
    )


def _shares(filters: dict) -> list[frappe._dict]:
    # A locking read also sees grants committed after this transaction's snapshot.
    return frappe.qb.get_query(
        "DocShare",
        fields=["name", "share_doctype", "share_name"],
        filters=filters,
        ignore_permissions=True,
        for_update=True,
    ).run(as_dict=True)


def _deny(message: str) -> NoReturn:
    frappe.throw(message, frappe.PermissionError)
