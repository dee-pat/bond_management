import hmac
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from io import BytesIO

import frappe
from frappe import _
from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError

from bond_management.bond_management.utils.financial import quantize_percent, to_decimal
from bond_management.bond_management.utils.private_attachment import read_private_pdf_attachment
from bond_management.bond_management.utils.statement_pdf import (
    normalize_account_number,
)

MAX_TRANSACTION_PDF_BYTES = 10 * 1024 * 1024
MAX_TRANSACTION_PDF_PAGES = 200
MAX_TRANSACTION_PDF_TEXT_CHARS = 2_000_000
MAX_POSITIONED_TEXT_FRAGMENTS = 100_000
POSITIONED_TEXT_Y_TOLERANCE = 2.5
ISIN_PATTERN = r"[A-Z]{2}[A-Z0-9]{10}"
NUMBER_PATTERN = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
ACCOUNT_PATTERN = re.compile(r"\bAccount\s+No\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE)
TRANSACTION_BLOCK_PATTERN = re.compile(
    r"(?P<body>\bBonds\s+Name\s*:[\s\S]*?"
    r"\bTransaction\s+Reference\s*:\s*(?P<reference>\S+))",
    re.IGNORECASE,
)

FIELD_PATTERN = re.compile(
    r"\b(?P<label>Bonds\s+Name|ISIN|Currency|Quantity(?:\s*/\s*Face\s+Value)?|"
    r"Face\s+Value|Price|Principal|Trade\s+Date|Settlement\s+Date|"
    r"Settlement\s+Amount(?:\s+in\s+Currency)?|Accrued\s+Interest|"
    r"Commission(?:\s*%|\s+Amount)?|Transaction\s+Reference)\s*:",
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
    principal: Decimal | None = None
    settlement_amount: Decimal | None = None


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
    principal: Decimal | None = None
    settlement_amount: Decimal | None = None


@dataclass(frozen=True)
class TransactionAttachmentDetails:
    portfolio_name: str
    account_no: str
    transactions: tuple[TransactionAttachmentRow, ...]


def transaction_attachment_row_values(
    row: TransactionAttachmentRow,
    portfolio_name: str | None = None,
) -> dict:
    """Return controller-independent Bond Transaction field values for a parsed row."""
    return {
        "transaction_reference": row.transaction_reference,
        "transaction_type": row.transaction_type,
        "isin": row.isin,
        "portfolio_name": portfolio_name or row.portfolio_name,
        "trade_date": row.trade_date,
        "settlement_date": row.settlement_date,
        "quantity_face_value": row.quantity_face_value,
        "price": row.price,
        "accrued_interest_paid": row.accrued_interest_paid,
        "commission": row.commission,
    }


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
        if not re.fullmatch(r"[RU]\d+", reference):
            raise TransactionPdfError("The transaction PDF contains an invalid Transaction Reference.")
        fields = _parse_row_fields(match.group("body"))
        settlement_date = _required_date(fields, "Settlement Date")
        trade_date = _optional_date(fields, "Trade Date") or settlement_date
        commission_percent, commission_amount = _parse_commission(fields)
        row = ParsedTransactionPdfRow(
            transaction_reference=reference,
            transaction_type="Sale" if reference.startswith("R") else "Purchase",
            isin=_parse_isin(fields),
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity_face_value=_parse_quantity_face_value(fields),
            price=_required_decimal(fields, "Price"),
            accrued_interest_paid=_required_decimal(fields, "Accrued Interest"),
            commission_percent=commission_percent,
            commission_amount=commission_amount,
            principal=_optional_decimal(fields, "Principal"),
            settlement_amount=_optional_decimal(fields, "Settlement Amount"),
        )
        _validate_transaction_row_values(row)
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
    content, _original_filename = read_private_pdf_attachment(
        attachment,
        max_bytes=MAX_TRANSACTION_PDF_BYTES,
        missing_message=_("Attach a PDF transaction confirmation before using automatic entry."),
        extension_message=_("Automatic Bond Transaction entry requires a PDF attachment."),
        private_message=_("Bond Transaction PDFs must be uploaded as private files."),
        size_message=_("The transaction PDF must be 10 MB or smaller."),
    )
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
        face_value_per_unit = face_values[row.isin]
        if row.principal is not None:
            pdf_face_value_per_unit = row.principal * Decimal("100") / (row.quantity_face_value * row.price)
            if pdf_face_value_per_unit <= 0:
                frappe.throw(
                    f"Transaction {row.transaction_reference} has a non-positive PDF Face Value Per Unit."
                )
            if pdf_face_value_per_unit.quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_EVEN
            ) != face_value_per_unit.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN):
                frappe.throw(
                    f"Face Value Per Unit for transaction {row.transaction_reference} does not match the PDF. "
                    f"PDF implies {pdf_face_value_per_unit:.4f}, but Bond Master has {face_value_per_unit:.4f}."
                )
        commission = row.commission_percent
        if commission is None:
            original_principal = row.quantity_face_value * face_value_per_unit
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
                principal=row.principal,
                settlement_amount=row.settlement_amount,
            )
        )

    return TransactionAttachmentDetails(
        portfolio_name=portfolio.portfolio_name,
        account_no=parsed.account_no,
        transactions=tuple(transactions),
    )


def _parse_reader(reader: PdfReader) -> ParsedTransactionPdf:
    try:
        page_count = len(reader.pages)
    except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError) as error:
        raise TransactionPdfError("The transaction PDF pages could not be read.") from error
    if page_count > MAX_TRANSACTION_PDF_PAGES:
        raise TransactionPdfError(
            f"The transaction PDF cannot contain more than {MAX_TRANSACTION_PDF_PAGES} pages."
        )
    if not page_count:
        raise TransactionPdfError("The transaction PDF has no pages.")
    text_length = 0
    try:
        page_texts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_length += len(page_text)
            if text_length > MAX_TRANSACTION_PDF_TEXT_CHARS:
                raise TransactionPdfError(
                    "The transaction PDF contains more text than the parser can safely process."
                )
            page_texts.append(page_text)
        text = "\n".join(page_texts)
    except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError) as error:
        raise TransactionPdfError("The transaction PDF pages could not be read.") from error

    try:
        return parse_transaction_pdf_text(text)
    except TransactionPdfError as plain_text_error:
        # Some Standard Chartered PDFs draw the labels for both columns first
        # and their values afterwards. Plain pypdf extraction therefore loses
        # the label/value relationship even though the PDF is visually clear.
        # Retry with the text fragments grouped by their page coordinates while
        # preserving the existing parser for older and simpler confirmations.
        try:
            positioned_pages = []
            positioned_fragment_count = 0
            for page in reader.pages:
                positioned_page, page_fragment_count = _extract_positioned_page_text(
                    page,
                    fragment_limit=MAX_POSITIONED_TEXT_FRAGMENTS - positioned_fragment_count,
                    include_fragment_count=True,
                )
                positioned_pages.append(positioned_page)
                positioned_fragment_count += page_fragment_count
        except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError):
            raise plain_text_error
        positioned_text = "\n".join(positioned_pages)
        if len(positioned_text) > MAX_TRANSACTION_PDF_TEXT_CHARS:
            raise TransactionPdfError("The positioned transaction PDF text exceeds the parser safety limit.")
        try:
            return parse_transaction_pdf_text(positioned_text)
        except TransactionPdfError:
            raise plain_text_error


def _extract_positioned_page_text(
    page,
    *,
    fragment_limit=MAX_POSITIONED_TEXT_FRAGMENTS,
    include_fragment_count=False,
) -> str | tuple[str, int]:
    """Rebuild readable rows from PDFs whose content stream is column-ordered."""
    fragments = []

    def visitor_text(text, _cm, tm, _font, _font_size):
        cleaned = " ".join((text or "").split())
        if cleaned:
            if len(fragments) >= fragment_limit:
                raise TransactionPdfError("The transaction PDF contains too many positioned text fragments.")
            fragments.append((float(tm[5]), float(tm[4]), cleaned))

    page.extract_text(visitor_text=visitor_text)

    rows = []
    rows_by_bucket = {}
    for y, x, text in fragments:
        bucket = round(y / POSITIONED_TEXT_Y_TOLERANCE)
        candidates = [
            rows_by_bucket[neighbor]
            for neighbor in (bucket - 1, bucket, bucket + 1)
            if neighbor in rows_by_bucket
        ]
        row = min(
            candidates,
            key=lambda candidate: abs(candidate[0] - y),
            default=None,
        )
        if row is None or abs(row[0] - y) > POSITIONED_TEXT_Y_TOLERANCE:
            row = [y, []]
            rows.append(row)
            rows_by_bucket[bucket] = row
        else:
            rows_by_bucket.setdefault(bucket, row)
        row[1].append((x, text))

    rows.sort(key=lambda row: row[0], reverse=True)
    positioned_text = "\n".join(
        " ".join(text for _x, text in sorted(fragments_for_row)) for _y, fragments_for_row in rows
    )
    return (positioned_text, len(fragments)) if include_fragment_count else positioned_text


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


def _parse_row_fields(text: str) -> dict[str, str]:
    matches = list(FIELD_PATTERN.finditer(text))
    fields = {}
    for index, match in enumerate(matches):
        label = " ".join(match.group("label").split()).title()
        label = re.sub(r"\s*/\s*", " / ", label)
        label = re.sub(r"\s*%", " %", label)
        label = label.removesuffix(" In Currency")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end() : end].strip()
        if label in fields and fields[label] != value:
            raise TransactionPdfError(f"The transaction PDF contains conflicting {label} values.")
        fields[label] = value
    return fields


def _parse_isin(fields: dict[str, str]) -> str:
    name_isins = set(re.findall(rf"\b{ISIN_PATTERN}\b", fields.get("Bonds Name", ""), re.IGNORECASE))
    isins = {value.upper() for value in name_isins}
    if "Isin" in fields:
        value = fields["Isin"].upper()
        if not re.fullmatch(ISIN_PATTERN, value):
            raise TransactionPdfError("The transaction PDF contains an invalid ISIN.")
        isins.add(value)
    if not isins:
        raise TransactionPdfError("Could not find ISIN in a transaction PDF row.")
    if len(isins) > 1:
        raise TransactionPdfError("The transaction PDF contains conflicting ISIN values.")
    return isins.pop()


def _required_value(fields: dict[str, str], label: str) -> str:
    if label not in fields:
        raise TransactionPdfError(f"Could not find {label} in a transaction PDF row.")
    return fields[label]


def _parse_decimal(value: str, label: str) -> Decimal:
    if not re.fullmatch(NUMBER_PATTERN, value):
        raise TransactionPdfError(f"The transaction PDF contains an invalid {label}: {value}.")
    return Decimal(value.replace(",", ""))


def _parse_quantity_face_value(fields: dict[str, str]) -> Decimal:
    values = [
        _parse_decimal(fields[label], "Quantity / Face Value")
        for label in ("Quantity", "Quantity / Face Value")
        if label in fields
    ]
    if not values:
        raise TransactionPdfError("Could not find Quantity / Face Value in a transaction PDF row.")
    if len(set(values)) > 1:
        raise TransactionPdfError("The transaction PDF contains conflicting Quantity / Face Value values.")
    return values[0]


def _required_decimal(fields: dict[str, str], label: str) -> Decimal:
    return _parse_decimal(_required_value(fields, label), label)


def _optional_decimal(fields: dict[str, str], label: str) -> Decimal | None:
    return _required_decimal(fields, label) if label in fields else None


def _required_date(fields: dict[str, str], label: str) -> date:
    return _parse_date(_required_value(fields, label), label)


def _optional_date(fields: dict[str, str], label: str) -> date | None:
    return _required_date(fields, label) if label in fields else None


def _parse_date(value: str, label: str) -> date:
    try:
        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
            raise ValueError("Invalid date format")
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError as error:
        raise TransactionPdfError(f"The transaction PDF contains an invalid {label}: {value}.") from error


def _parse_commission(fields: dict[str, str]) -> tuple[Decimal | None, Decimal | None]:
    percent = None
    amount = None
    if "Commission %" in fields:
        value = fields["Commission %"]
        if value == "%":
            raise TransactionPdfError("The transaction PDF contains an invalid Commission %.")
        value = value.removesuffix("%").strip()
        if value:
            percent = (
                Decimal("0")
                if re.fullmatch(r"N/?A", value, re.IGNORECASE)
                else _parse_decimal(value, "Commission %")
            )
    for label in ("Commission Amount", "Commission"):
        if label in fields:
            value = fields[label]
            parsed_amount = (
                Decimal("0")
                if not value or re.fullmatch(r"N/?A", value, re.IGNORECASE)
                else _parse_decimal(value, label)
            )
            if parsed_amount < 0:
                raise TransactionPdfError("Commission Amount must be zero or greater.")
            if amount is not None and amount != parsed_amount:
                raise TransactionPdfError(
                    "The transaction PDF contains conflicting Commission Amount values."
                )
            amount = parsed_amount
    if percent is not None:
        # A valid percentage is the primary source; amount labels still must be valid.
        return percent, None
    if amount is not None:
        if all(
            not fields.get(label) or re.fullmatch(r"N/?A", fields[label], re.IGNORECASE)
            for label in ("Commission Amount", "Commission")
        ):
            return Decimal("0"), None
        return None, amount
    if "Commission %" in fields:
        return Decimal("0"), None
    raise TransactionPdfError("Could not find Commission in a transaction PDF row.")


def _validate_transaction_row_values(row: ParsedTransactionPdfRow) -> None:
    for value, label in (
        (row.quantity_face_value, "Quantity / Face Value"),
        (row.price, "Price"),
    ):
        if value <= 0:
            raise TransactionPdfError(f"{label} must be greater than zero.")

    for value, label in (
        (row.accrued_interest_paid, "Accrued Interest"),
        (row.commission_percent, "Commission %"),
        (row.commission_amount, "Commission Amount"),
    ):
        if value is not None and value < 0:
            raise TransactionPdfError(f"{label} must be zero or greater.")

    for value, label in (
        (row.principal, "Principal"),
        (row.settlement_amount, "Settlement Amount"),
    ):
        if value is not None and value <= 0:
            raise TransactionPdfError(f"{label} must be greater than zero.")
