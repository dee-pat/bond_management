import re

import frappe
from frappe import _
from frappe.utils import getdate

from bond_management.bond_management.utils.private_attachment import (
    standardize_private_pdf_attachment,
)
from bond_management.bond_management.utils.statement_pdf import normalize_account_number

TRANSACTION_FILENAME_PREFIX = "Transaction-"
SAFE_ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def get_standard_transaction_filename(account_no: str, settlement_date) -> str:
    """Return the canonical private PDF filename for a Bond Transaction."""
    normalized_account = normalize_account_number(account_no)
    if not normalized_account or not SAFE_ACCOUNT_PATTERN.fullmatch(normalized_account):
        frappe.throw(_("Product Account No. contains characters that cannot be used in a filename."))

    return (
        f"{TRANSACTION_FILENAME_PREFIX}{normalized_account}-{getdate(settlement_date).strftime('%Y%m%d')}.pdf"
    )


def standardize_transaction_attachment(transaction, account_no: str, settlement_date) -> str:
    """Rename a transaction's private PDF and attach it to the transaction document."""
    expected_filename = get_standard_transaction_filename(account_no, settlement_date)
    return standardize_private_pdf_attachment(transaction, expected_filename)
