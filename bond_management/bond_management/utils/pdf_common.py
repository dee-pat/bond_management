"""Shared opening and credential lookup for password-protected bank PDFs."""

from dataclasses import dataclass, field
from io import BytesIO

import frappe
from frappe.utils.password import get_decrypted_password
from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError

MAX_PDF_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class PortfolioPdfCredentials:
    portfolio_name: str
    account_no: str
    transaction_account_no: str | None = None
    password: str | None = field(default=None, repr=False)


def open_pdf(
    content: bytes,
    passwords: list[str],
    *,
    error_class: type[ValueError],
    password_error_class: type[ValueError],
    size_message: str,
    password_message: str,
) -> tuple[PdfReader, str | None]:
    """Return a readable PDF and the configured password that unlocked it, if any.

    The caller parses the returned reader itself. A parsing error after a
    successful decrypt must surface as-is rather than masking it as a password
    failure by trying the next password.
    """
    if len(content) > MAX_PDF_BYTES:
        raise error_class(size_message)
    if b"%PDF-" not in content[:1024]:
        raise error_class("The attachment is not a valid PDF file.")

    try:
        probe = PdfReader(BytesIO(content), strict=False)
    except (PdfReadError, PdfStreamError, ValueError) as error:
        raise error_class("The attachment could not be read as a PDF.") from error

    if not probe.is_encrypted:
        return probe, None

    for password in dict.fromkeys(password for password in passwords if password):
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if not reader.decrypt(password):
                continue
        except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError, ValueError):
            continue
        return reader, password

    raise password_error_class(password_message)


def get_portfolio_pdf_credentials() -> list[PortfolioPdfCredentials]:
    """Return readable portfolios with their configured PDF passwords."""
    portfolios = frappe.qb.get_query(
        "Bond Portfolio",
        fields=["name", "account_no", "transaction_account_no"],
        order_by="name asc",
        ignore_permissions=False,
    ).run(as_dict=True)
    # The portfolio rows above are permission-filtered; decrypt only their passwords.
    return [
        PortfolioPdfCredentials(
            portfolio_name=portfolio.name,
            account_no=portfolio.account_no,
            transaction_account_no=portfolio.transaction_account_no,
            password=get_decrypted_password(
                "Bond Portfolio",
                portfolio.name,
                "statement_pdf_password",
                raise_exception=False,
            ),
        )
        for portfolio in portfolios
    ]
