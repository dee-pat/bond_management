import re

import frappe
from frappe import _
from frappe.utils import getdate

from bond_management.bond_management.utils.private_attachment import (
    standardize_private_pdf_attachment,
)
from bond_management.bond_management.utils.statement_pdf import normalize_account_number

STATEMENT_FILENAME_PREFIX = "PortfolioStatement-"
SAFE_ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def get_standard_statement_filename(account_no: str, statement_date) -> str:
    """Return the canonical private PDF filename for a Bond Statement."""
    normalized_account = normalize_account_number(account_no)
    if not normalized_account or not SAFE_ACCOUNT_PATTERN.fullmatch(normalized_account):
        frappe.throw(_("Product Account No. contains characters that cannot be used in a filename."))

    return f"{STATEMENT_FILENAME_PREFIX}{normalized_account}-{getdate(statement_date).strftime('%Y%m%d')}.pdf"


def standardize_statement_attachment(statement, account_no: str, statement_date) -> str:
    """Rename a statement's private PDF and File record to its canonical filename."""
    expected_filename = get_standard_statement_filename(account_no, statement_date)
    return standardize_private_pdf_attachment(statement, expected_filename)
