"""Shared opening, text limits, and account identity for password-protected bank PDFs."""

import hmac
import re
from dataclasses import dataclass, field
from io import BytesIO

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password
from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 200
MAX_PDF_TEXT_CHARS = 2_000_000
PDF_READ_ERRORS = (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError)
ISIN_PATTERN = r"[A-Z]{2}[A-Z0-9]{10}"
NUMBER_PATTERN = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
SAFE_ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


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
        except (*PDF_READ_ERRORS, ValueError):
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


def extract_page_texts(reader: PdfReader, *, error_class: type[ValueError], label: str) -> list[str]:
    """Return each page's text after enforcing the page-count and total-text safety limits."""
    try:
        page_count = len(reader.pages)
    except PDF_READ_ERRORS as error:
        raise error_class(f"The {label} PDF pages could not be read.") from error
    if page_count > MAX_PDF_PAGES:
        raise error_class(f"The {label} PDF cannot contain more than {MAX_PDF_PAGES} pages.")
    if not page_count:
        raise error_class(f"The {label} PDF has no pages.")

    page_texts = []
    text_length = 0
    try:
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_length += len(page_text)
            if text_length > MAX_PDF_TEXT_CHARS:
                raise error_class(f"The {label} PDF contains more text than the parser can safely process.")
            page_texts.append(page_text)
    except PDF_READ_ERRORS as error:
        raise error_class(f"The {label} PDF pages could not be read.") from error
    return page_texts


def normalize_account_number(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def filename_account(account_no: str) -> str:
    """Return the normalized account number, rejecting characters unsafe in a filename."""
    normalized_account = normalize_account_number(account_no)
    if not normalized_account or not SAFE_ACCOUNT_PATTERN.fullmatch(normalized_account):
        frappe.throw(_("Product Account No. contains characters that cannot be used in a filename."))
    return normalized_account


def match_account_portfolio(
    credentials: list[PortfolioPdfCredentials], account_no: str, *, reattach: str
) -> PortfolioPdfCredentials:
    """Return the one readable portfolio whose Account No or Transaction Account No is ``account_no``."""
    matching = [
        credential
        for credential in credentials
        if account_no
        in {
            normalize_account_number(credential.account_no),
            normalize_account_number(credential.transaction_account_no),
        }
    ]
    if not matching:
        frappe.throw(
            _(
                "No accessible Bond Portfolio has account number {0}. Add it as Account No or Transaction Account No on Bond Portfolio, then {1}."
            ).format(account_no, reattach)
        )
    if len(matching) > 1:
        frappe.throw(
            _(
                "More than one Bond Portfolio uses account number {0}. Account No and Transaction Account No values must identify only one portfolio."
            ).format(account_no)
        )
    return matching[0]


def unlocked_with_own_password(portfolio: PortfolioPdfCredentials, unlock_password: str | None) -> bool:
    """Whether the password that opened the PDF, if any, is the matched portfolio's own."""
    return unlock_password is None or bool(
        portfolio.password and hmac.compare_digest(portfolio.password, unlock_password)
    )
