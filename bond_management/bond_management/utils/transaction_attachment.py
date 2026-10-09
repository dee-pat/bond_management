import hashlib
import re

import frappe
from frappe import _
from frappe.utils import getdate

from bond_management.bond_management.utils.private_attachment import (
    read_private_pdf_attachment,
    standardize_private_pdf_attachment,
)
from bond_management.bond_management.utils.statement_pdf import normalize_account_number
from bond_management.bond_management.utils.transaction_pdf import MAX_TRANSACTION_PDF_BYTES

TRANSACTION_FILENAME_PREFIX = "Transaction-"
SAFE_ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
FILE_NAME_MAX_LENGTH = 140


def get_standard_transaction_filename(
    account_no: str, settlement_date, *, content: bytes | None = None
) -> str:
    """Return the canonical private PDF filename for a Bond Transaction."""
    normalized_account = normalize_account_number(account_no)
    if not normalized_account or not SAFE_ACCOUNT_PATTERN.fullmatch(normalized_account):
        frappe.throw(_("Product Account No. contains characters that cannot be used in a filename."))

    settlement_date_component = getdate(settlement_date).strftime("%Y%m%d")
    if content is not None:
        content_digest = hashlib.sha256(content).hexdigest()
        static_length = (
            len(TRANSACTION_FILENAME_PREFIX)
            + 1
            + len(settlement_date_component)
            + 1
            + len(content_digest)
            + len(".pdf")
        )
        max_account_length = FILE_NAME_MAX_LENGTH - static_length
        if len(normalized_account) > max_account_length:
            content_digest = hashlib.sha256(normalized_account.encode("ascii") + b"\0" + content).hexdigest()
            normalized_account = normalized_account[:max_account_length]

        return (
            f"{TRANSACTION_FILENAME_PREFIX}{normalized_account}-{settlement_date_component}"
            f"-{content_digest}.pdf"
        )

    return f"{TRANSACTION_FILENAME_PREFIX}{normalized_account}-{settlement_date_component}.pdf"


def standardize_transaction_attachment(transaction, account_no: str, settlement_date) -> str:
    """Rename a transaction's private PDF and attach it to the transaction document."""
    legacy_filename = get_standard_transaction_filename(account_no, settlement_date)
    legacy_url = f"/private/files/{legacy_filename}"
    existing_attachment = None
    if transaction.name and not transaction.is_new():
        existing_attachment = frappe.db.get_value("Bond Transaction", transaction.name, "attachment")

    if transaction.attachment == legacy_url and existing_attachment == legacy_url:
        # Keep links to previously standardized confirmations stable.
        return standardize_private_pdf_attachment(transaction, legacy_filename)

    content, _original_filename = read_private_pdf_attachment(
        transaction.attachment,
        max_bytes=MAX_TRANSACTION_PDF_BYTES,
        missing_message=_("Attach a PDF before standardizing its filename."),
        extension_message=_("Automatic Bond Transaction entry requires a PDF attachment."),
        private_message=_("Bond Transaction PDFs must be uploaded as private files."),
        size_message=_("The transaction PDF must be 10 MB or smaller."),
    )
    expected_filename = get_standard_transaction_filename(account_no, settlement_date, content=content)
    return standardize_private_pdf_attachment(transaction, expected_filename)
