from pathlib import Path

import frappe
from frappe import _
from frappe.utils import getdate

from bond_management.bond_management.utils.pdf_common import filename_account, normalize_account_number
from bond_management.bond_management.utils.private_attachment import (
    FILE_NAME_MAX_LENGTH,
    standardize_private_pdf_attachment,
)

STATEMENT_FILENAME_PREFIX = "PortfolioStatement-"


def get_standard_statement_filename(account_no: str, statement_date) -> str:
    """Return the canonical private PDF filename for a Bond Statement."""
    return f"{STATEMENT_FILENAME_PREFIX}{filename_account(account_no)}-{getdate(statement_date).strftime('%Y%m%d')}.pdf"


def standardize_statement_attachment(statement, account_no: str, statement_date) -> str:
    """Rename a statement PDF, versioning distinct content at the same account/date."""
    expected_filename = get_standard_statement_filename(account_no, statement_date)
    return standardize_private_pdf_attachment(
        statement,
        expected_filename,
        conflict_filename=lambda digest: get_versioned_statement_filename(account_no, statement_date, digest),
    )


def get_versioned_statement_filename(account_no: str, statement_date, digest: str) -> str:
    """Preserve the full legacy account hint within File's filename limit."""
    canonical_filename = get_standard_statement_filename(account_no, statement_date)
    filename = f"{Path(canonical_filename).stem}-{digest}.pdf"
    if len(filename) <= FILE_NAME_MAX_LENGTH:
        return filename

    # The content hash identifies the revision; omitting the date leaves room
    # for the full account and at least 24 hash characters for canonical names
    # that already fit File's 140-character Data field.
    prefix = f"PS-{normalize_account_number(account_no)}-"
    digest_length = FILE_NAME_MAX_LENGTH - len(prefix) - len(".pdf")
    if digest_length < 24:
        frappe.throw(_("Product Account No. is too long for a versioned statement filename."))
    return f"{prefix}{digest[:digest_length]}.pdf"
