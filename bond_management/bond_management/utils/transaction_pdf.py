import hmac
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

import frappe
from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError

from bond_management.bond_management.utils.financial import quantize_percent, to_decimal
from bond_management.bond_management.utils.statement_pdf import (
    normalize_account_number,
)

MAX_TRANSACTION_PDF_BYTES = 10 * 1024 * 1024
ISIN_PATTERN = r"[A-Z]{2}[A-Z0-9]{10}"
NUMBER_PATTERN = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
ACCOUNT_PATTERN = re.compile(r"\bAccount\s+No\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE)
TRANSACTION_BLOCK_PATTERN = re.compile(
    r"\bBonds\s+Name\s*:"
    r"(?P<body>[\s\S]*?\bTransaction\s+Reference\s*:\s*(?P<reference>[RU]\d+)\b)",
    re.IGNORECASE,
)


class TransactionPdfError(ValueError):
    pass


class TransactionPdfPasswordError(TransactionPdfError):
    pass


@dataclass(frozen=True)
class TransactionPortfolioPdfCredentials:
    portfolio_name: str
    account_no: str
    transaction_account_no: str | None = None
    password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ParsedTransactionPdfRow:
    transaction_reference: str
    transaction_type: str
    isin: str
    trade_date: date
    settlement_date: date
    quantity_face_value: Decimal
    price: Decimal
    accrued_interest_paid: Decimal
    commission_percent: Decimal | None
    commission_amount: Decimal | None


@dataclass(frozen=True)
class ParsedTransactionPdf:
    account_no: str
    transactions: tuple[ParsedTransactionPdfRow, ...]
    unlock_password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class TransactionAttachmentRow:
    transaction_reference: str
    transaction_type: str
    isin: str
    portfolio_name: str
    trade_date: date
    settlement_date: date
    quantity_face_value: Decimal
    price: Decimal
    accrued_interest_paid: Decimal
    commission: Decimal


@dataclass(frozen=True)
class TransactionAttachmentDetails:
    portfolio_name: str
    account_no: str
    transactions: tuple[TransactionAttachmentRow, ...]


def parse_transaction_pdf_text(text: str) -> ParsedTransactionPdf:
    """Parse all bond confirmations contained in current or legacy bank PDF text."""
    account_numbers = {normalize_account_number(match) for match in ACCOUNT_PATTERN.findall(text or "")}
    if not account_numbers:
        raise TransactionPdfError("Could not find Account No. in the transaction PDF.")
    if len(account_numbers) > 1:
        raise TransactionPdfError("The transaction PDF contains conflicting account numbers.")

    rows_by_reference = {}
    for match in TRANSACTION_BLOCK_PATTERN.finditer(text or ""):
        reference = match.group("reference").upper()
        body = match.group("body")
        settlement_date = _required_date(body, "Settlement Date")
        trade_date = _optional_date(body, "Trade Date") or settlement_date
        commission_percent, commission_amount = _parse_commission(body)
        row = ParsedTransactionPdfRow(
            transaction_reference=reference,
            transaction_type="Sale" if reference.startswith("R") else "Purchase",
            isin=_required_match(body, rf"\b(?P<value>{ISIN_PATTERN})\b", "ISIN").upper(),
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity_face_value=_required_decimal(
                body,
                rf"\bQuantity(?:\s*/\s*Face\s+Value)?\s*:\s*(?P<value>{NUMBER_PATTERN})",
                "Quantity / Face Value",
            ),
            price=_required_decimal(
                body,
                rf"\bPrice\s*:\s*(?P<value>{NUMBER_PATTERN})",
                "Price",
            ),
            accrued_interest_paid=_required_decimal(
                body,
                rf"\bAccrued\s+Interest\s*:\s*(?P<value>{NUMBER_PATTERN})",
                "Accrued Interest",
            ),
            commission_percent=commission_percent,
            commission_amount=commission_amount,
        )
        existing = rows_by_reference.get(reference)
        if existing and existing != row:
            raise TransactionPdfError(
                f"The transaction PDF contains conflicting values for reference {reference}."
            )
        rows_by_reference[reference] = row

    if not rows_by_reference:
        raise TransactionPdfError(
            "Could not find a bond transaction with a reference starting with R or U in the PDF."
        )

    return ParsedTransactionPdf(
        account_no=account_numbers.pop(),
        transactions=tuple(rows_by_reference.values()),
    )


def extract_transaction_pdf(content: bytes, passwords: list[str]) -> ParsedTransactionPdf:
    """Decrypt a transaction PDF with configured portfolio passwords and parse every trade."""
    if len(content) > MAX_TRANSACTION_PDF_BYTES:
        raise TransactionPdfError("The transaction PDF must be 10 MB or smaller.")
    if b"%PDF-" not in content[:1024]:
        raise TransactionPdfError("The attachment is not a valid PDF file.")

    try:
        probe = PdfReader(BytesIO(content), strict=False)
    except (PdfReadError, PdfStreamError, ValueError) as error:
        raise TransactionPdfError("The attachment could not be read as a PDF.") from error

    if not probe.is_encrypted:
        return _parse_reader(probe)

    for password in dict.fromkeys(password for password in passwords if password):
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if not reader.decrypt(password):
                continue
        except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError, ValueError):
            continue
        # Once decryption succeeds, report the real format/parsing error instead
        # of incorrectly trying the next password and masking it as a password error.
        parsed = _parse_reader(reader)
        return ParsedTransactionPdf(
            account_no=parsed.account_no,
            transactions=parsed.transactions,
            unlock_password=password,
        )

    raise TransactionPdfPasswordError(
        "The transaction PDF could not be unlocked with any configured Bond Portfolio password."
    )


def get_transaction_attachment_details(attachment: str) -> TransactionAttachmentDetails:
    """Read a private confirmation PDF and resolve its account, bonds, and commission rates."""
    content = _read_private_transaction_attachment(attachment)
    credentials = _get_portfolio_credentials()
    try:
        parsed = extract_transaction_pdf(
            content,
            [credential.password for credential in credentials if credential.password],
        )
    except TransactionPdfError as error:
        frappe.throw(str(error))

    portfolio = _resolve_portfolio(parsed, credentials)
    parsed_isins = [row.isin for row in parsed.transactions]
    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=["name", "face_value_per_unit"],
        filters={"name": ["in", parsed_isins]},
        ignore_permissions=False,
    ).run(as_dict=True)
    face_values = {bond.name: to_decimal(bond.face_value_per_unit, "Face Value Per Unit") for bond in bonds}
    missing_isins = sorted(set(parsed_isins) - set(face_values))
    if missing_isins:
        frappe.throw(
            f"No accessible Bond Master exists for the transaction PDF ISINs: {', '.join(missing_isins)}."
        )

    transactions = []
    for row in parsed.transactions:
        if row.quantity_face_value != row.quantity_face_value.to_integral_value():
            frappe.throw(f"Transaction {row.transaction_reference} has a non-whole Quantity / Face Value.")
        commission = row.commission_percent
        if commission is None:
            original_principal = row.quantity_face_value * face_values[row.isin]
            if original_principal <= 0:
                frappe.throw(
                    f"Transaction {row.transaction_reference} must have a positive original principal."
                )
            commission = row.commission_amount / original_principal * Decimal("100")

        transactions.append(
            TransactionAttachmentRow(
                transaction_reference=row.transaction_reference,
                transaction_type=row.transaction_type,
                isin=row.isin,
                portfolio_name=portfolio.portfolio_name,
                trade_date=row.trade_date,
                settlement_date=row.settlement_date,
                quantity_face_value=row.quantity_face_value,
                price=row.price,
                accrued_interest_paid=row.accrued_interest_paid,
                commission=quantize_percent(commission),
            )
        )

    return TransactionAttachmentDetails(
        portfolio_name=portfolio.portfolio_name,
        account_no=parsed.account_no,
        transactions=tuple(transactions),
    )


def _parse_reader(reader: PdfReader) -> ParsedTransactionPdf:
    if not reader.pages:
        raise TransactionPdfError("The transaction PDF has no pages.")
    try:
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError) as error:
        raise TransactionPdfError("The transaction PDF pages could not be read.") from error
    return parse_transaction_pdf_text(text)


def _read_private_transaction_attachment(attachment: str) -> bytes:
    if not attachment:
        frappe.throw("Attach a PDF transaction confirmation before using automatic entry.")
    if not attachment.lower().endswith(".pdf"):
        frappe.throw("Automatic Bond Transaction entry requires a PDF attachment.")

    files = frappe.qb.get_query(
        "File",
        fields=["name"],
        filters={"file_url": attachment},
        order_by="creation desc",
        limit=1,
        ignore_permissions=False,
    ).run(pluck=True)
    if not files:
        frappe.throw("The attached PDF was not found or you do not have permission to read it.")

    file_doc = frappe.get_doc("File", files[0])
    file_doc.check_permission("read")
    if not file_doc.is_private:
        frappe.throw("Bond Transaction PDFs must be uploaded as private files.")

    file_path = Path(file_doc.get_full_path()).resolve()
    private_files_path = Path(frappe.get_site_path("private", "files")).resolve()
    if not file_path.is_relative_to(private_files_path) or not file_path.is_file():
        frappe.throw("The attached private PDF could not be found.")
    if file_path.stat().st_size > MAX_TRANSACTION_PDF_BYTES:
        frappe.throw("The transaction PDF must be 10 MB or smaller.")
    return file_path.read_bytes()


def _get_portfolio_credentials() -> list[TransactionPortfolioPdfCredentials]:
    portfolios = frappe.qb.get_query(
        "Bond Portfolio",
        fields=["name", "account_no", "transaction_account_no"],
        order_by="name asc",
        ignore_permissions=False,
    ).run(as_dict=True)
    credentials = []
    for portfolio in portfolios:
        portfolio_doc = frappe.get_doc("Bond Portfolio", portfolio.name)
        credentials.append(
            TransactionPortfolioPdfCredentials(
                portfolio_name=portfolio.name,
                account_no=portfolio.account_no,
                transaction_account_no=portfolio.transaction_account_no,
                password=portfolio_doc.get_password(
                    "statement_pdf_password",
                    raise_exception=False,
                ),
            )
        )
    return credentials


def _resolve_portfolio(
    parsed: ParsedTransactionPdf,
    credentials: list[TransactionPortfolioPdfCredentials],
) -> TransactionPortfolioPdfCredentials:
    matching = [
        credential
        for credential in credentials
        if parsed.account_no
        in {
            normalize_account_number(credential.account_no),
            normalize_account_number(credential.transaction_account_no),
        }
    ]
    if not matching:
        frappe.throw(
            f"No accessible Bond Portfolio has account number {parsed.account_no}. "
            "Add it as Account No or Transaction Account No on Bond Portfolio, "
            "then attach the confirmation again."
        )
    if len(matching) > 1:
        frappe.throw(
            f"More than one Bond Portfolio uses account number {parsed.account_no}. "
            "Account No and Transaction Account No values must identify only one portfolio."
        )

    portfolio = matching[0]
    if parsed.unlock_password is not None and (
        not portfolio.password or not hmac.compare_digest(portfolio.password, parsed.unlock_password)
    ):
        frappe.throw(
            f"The configured PDF password for portfolio {portfolio.portfolio_name} "
            "does not unlock this transaction confirmation."
        )
    return portfolio


def _required_match(text: str, pattern: str, label: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        raise TransactionPdfError(f"Could not find {label} in a transaction PDF row.")
    return match.group("value")


def _required_decimal(text: str, pattern: str, label: str) -> Decimal:
    value = _required_match(text, pattern, label)
    try:
        parsed = Decimal(value.replace(",", ""))
    except InvalidOperation as error:
        raise TransactionPdfError(f"The transaction PDF contains an invalid {label}: {value}.") from error
    if not parsed.is_finite():
        raise TransactionPdfError(f"The transaction PDF contains a non-finite {label}.")
    return parsed


def _required_date(text: str, label: str) -> date:
    value = _required_match(
        text,
        rf"\b{re.escape(label)}\s*:\s*(?P<value>\d{{2}}/\d{{2}}/\d{{4}})",
        label,
    )
    return _parse_date(value, label)


def _optional_date(text: str, label: str) -> date | None:
    match = re.search(
        rf"\b{re.escape(label)}\s*:\s*(?P<value>\d{{2}}/\d{{2}}/\d{{4}})",
        text,
        re.IGNORECASE,
    )
    return _parse_date(match.group("value"), label) if match else None


def _parse_date(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError as error:
        raise TransactionPdfError(f"The transaction PDF contains an invalid {label}: {value}.") from error


def _parse_commission(text: str) -> tuple[Decimal | None, Decimal | None]:
    percent_match = re.search(
        rf"\bCommission\s*%\s*:\s*(?P<value>N/?A|{NUMBER_PATTERN})\s*%?",
        text,
        re.IGNORECASE,
    )
    if percent_match:
        value = percent_match.group("value")
        return (Decimal("0") if re.fullmatch(r"N/?A", value, re.IGNORECASE) else Decimal(value), None)

    amount_match = re.search(
        rf"\bCommission(?:\s+Amount)?\s*:\s*(?P<value>{NUMBER_PATTERN})",
        text,
        re.IGNORECASE,
    )
    if amount_match:
        return None, Decimal(amount_match.group("value").replace(",", ""))

    if re.search(r"\bCommission(?:\s*%|\s+Amount)?\s*:", text, re.IGNORECASE):
        return Decimal("0"), None

    raise TransactionPdfError("Could not find Commission in a transaction PDF row.")
