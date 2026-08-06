import hmac
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

import frappe
from frappe import _
from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError

from bond_management.bond_management.utils.validation import optional_string

MAX_STATEMENT_PDF_BYTES = 10 * 1024 * 1024
DATE_PATTERNS = (
    re.compile(r"Portfolio\s+Summary\s+as\s+of\s+(\d{2}/\d{2}/\d{4})", re.IGNORECASE),
    re.compile(
        r"SUMMARY\s+OF\s+ACCOUNT\b[\s\S]{0,250}?\bAs\s+of\s+(\d{2}/\d{2}/\d{4})",
        re.IGNORECASE,
    ),
)
ACCOUNT_PATTERNS = (
    re.compile(r"\bProduct\s+Account\s+No\.?\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE),
    re.compile(r"\bIS\s+Account\s*:\s*([A-Za-z0-9-]+)", re.IGNORECASE),
)
ISIN_PATTERN = r"[A-Z]{2}[A-Z0-9]{10}"
NUMBER_PATTERN = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
CURRENCY_CODE_PATTERN = r"[A-Z]{3}"
CURRENCY_RATE_PATTERN = re.compile(
    rf"\b(?P<from_currency>{CURRENCY_CODE_PATTERN})\s*/\s*"
    rf"(?P<to_currency>{CURRENCY_CODE_PATTERN})\s+(?P<rate>{NUMBER_PATTERN})\b",
    re.IGNORECASE,
)
CURRENT_MARKET_PRICE_PATTERN = re.compile(
    rf"\b(?P<isin>{ISIN_PATTERN})\s+"
    rf"(?P<reported_quantity>{NUMBER_PATTERN})\s+"
    rf"{NUMBER_PATTERN}\s+{NUMBER_PATTERN}\s+{NUMBER_PATTERN}\s+"
    rf"\d{{2}}/\d{{2}}/\d{{4}}\s+(?P<market_price>{NUMBER_PATTERN})\b"
)
LEGACY_MARKET_PRICE_PATTERN = re.compile(
    rf"\b(?P<isin>{ISIN_PATTERN})\s+[A-Z]{{3}}\s+"
    rf"(?P<reported_quantity>{NUMBER_PATTERN})\s+"
    rf"{NUMBER_PATTERN}\s+{NUMBER_PATTERN}\s+"
    rf"(?P<market_price>{NUMBER_PATTERN})\s+"
    rf"{NUMBER_PATTERN}\s+(?P<market_value>{NUMBER_PATTERN})\s+"
    rf"\d{{2}}/\d{{2}}/\d{{4}}\b"
)
ACCOUNT_FILENAME_PATTERN = re.compile(
    r"\bPortfolioStatement[-_](?P<account_no>[A-Za-z0-9-]+)[-_]\d{8}\.pdf$",
    re.IGNORECASE,
)
LEGACY_NAMED_MARKET_PRICE_PATTERN = re.compile(
    rf"(?P<bond_name>[^\n]+?)\s+{CURRENCY_CODE_PATTERN}\s+"
    rf"(?P<reported_quantity>{NUMBER_PATTERN})\s+"
    rf"{NUMBER_PATTERN}\s+{NUMBER_PATTERN}\s+"
    rf"(?P<market_price>{NUMBER_PATTERN})\s+"
    rf"{NUMBER_PATTERN}\s+(?P<market_value>{NUMBER_PATTERN})\s+"
    rf"\d{{2}}/\d{{2}}/\d{{4}}\b",
    re.IGNORECASE,
)


class StatementPdfError(ValueError):
    pass


class StatementPdfPasswordError(StatementPdfError):
    pass


@dataclass(frozen=True)
class ParsedMarketPrice:
    isin: str
    market_price: Decimal
    reported_quantity: Decimal
    quantity_is_face_value: bool


@dataclass(frozen=True)
class ParsedExchangeRate:
    from_currency: str
    to_currency: str
    rate: Decimal


@dataclass(frozen=True)
class ParsedStatementPdf:
    account_no: str
    statement_date: date
    market_prices: tuple[ParsedMarketPrice, ...] = ()
    exchange_rates: tuple[ParsedExchangeRate, ...] = ()
    unlock_password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class PortfolioPdfCredentials:
    portfolio_name: str
    account_no: str
    transaction_account_no: str | None = None
    password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class StatementAttachmentDetails:
    portfolio_name: str
    account_no: str
    portfolio_account_no: str
    statement_date: date
    market_prices: tuple[ParsedMarketPrice, ...] = ()
    exchange_rates: tuple[ParsedExchangeRate, ...] = ()


def parse_statement_pdf_text(
    text: str,
    account_no_hint: str | None = None,
) -> ParsedStatementPdf:
    """Extract the account and statement date from supported bank statement layouts."""
    account_numbers = _unique_matches(text, ACCOUNT_PATTERNS, normalize_account_number)
    if not account_numbers:
        if re.search(
            r"\bBonds\s*-\s*Confirmation\s+Notice\b|\bTransaction\s+Reference\b",
            text or "",
            re.IGNORECASE,
        ):
            raise StatementPdfError(
                "This PDF is a Bond Transaction confirmation, not a Bond Statement. "
                "Attach it on a new Bond Transaction instead."
            )
        if account_no_hint:
            account_numbers = [normalize_account_number(account_no_hint)]
        else:
            raise StatementPdfError(
                "Could not find Product Account No. or IS Account in the PDF or its original filename."
            )
    if len(account_numbers) > 1:
        raise StatementPdfError("The PDF contains conflicting product account numbers.")

    statement_dates = _unique_matches(text, DATE_PATTERNS, _parse_statement_date)
    if not statement_dates:
        raise StatementPdfError(
            "Could not find Portfolio Summary as of or SUMMARY OF ACCOUNT As of in the first PDF page."
        )
    if len(statement_dates) > 1:
        raise StatementPdfError("The PDF contains conflicting portfolio summary dates.")

    return ParsedStatementPdf(
        account_no=account_numbers[0],
        statement_date=statement_dates[0],
    )


def parse_statement_market_prices(
    text: str,
    bond_name_to_isin: Mapping[str, str] | None = None,
) -> tuple[ParsedMarketPrice, ...]:
    """Extract fixed-income ISIN prices from current and legacy statement tables."""
    rows_by_isin: dict[str, ParsedMarketPrice] = {}
    for pattern in (CURRENT_MARKET_PRICE_PATTERN, LEGACY_MARKET_PRICE_PATTERN):
        for match in pattern.finditer(text or ""):
            isin = match.group("isin").upper()
            try:
                market_price = Decimal(match.group("market_price").replace(",", ""))
                reported_quantity = Decimal(match.group("reported_quantity").replace(",", ""))
            except InvalidOperation as error:
                raise StatementPdfError(
                    f"The PDF contains invalid fixed-income values for ISIN {isin}."
                ) from error
            if not market_price.is_finite() or market_price <= 0:
                raise StatementPdfError(f"The PDF market price for ISIN {isin} must be greater than zero.")
            if not reported_quantity.is_finite() or reported_quantity < 0:
                raise StatementPdfError(f"The PDF reported quantity for ISIN {isin} must be zero or greater.")

            quantity_is_face_value = False
            if pattern is LEGACY_MARKET_PRICE_PATTERN:
                market_value = Decimal(match.group("market_value").replace(",", ""))
                if not market_value.is_finite() or market_value < 0:
                    raise StatementPdfError(f"The PDF market value for ISIN {isin} must be zero or greater.")
                quantity_is_face_value = _legacy_quantity_is_monetary_nominal(
                    reported_quantity,
                    market_price,
                    market_value,
                )

            parsed_row = ParsedMarketPrice(
                isin=isin,
                market_price=market_price,
                reported_quantity=reported_quantity,
                quantity_is_face_value=quantity_is_face_value,
            )
            existing_row = rows_by_isin.get(isin)
            if existing_row and existing_row.market_price != market_price:
                raise StatementPdfError(f"The PDF contains conflicting market prices for ISIN {isin}.")
            if existing_row and (
                existing_row.reported_quantity != reported_quantity
                or existing_row.quantity_is_face_value != quantity_is_face_value
            ):
                raise StatementPdfError(f"The PDF contains conflicting reported quantities for ISIN {isin}.")
            rows_by_isin[isin] = parsed_row

    normalized_bond_name_to_isin = {}
    for name, isin in (bond_name_to_isin or {}).items():
        for alias in _bond_name_aliases(name):
            normalized_bond_name_to_isin[alias] = isin
    for match in LEGACY_NAMED_MARKET_PRICE_PATTERN.finditer(text or ""):
        bond_name = match.group("bond_name").strip()
        if re.fullmatch(ISIN_PATTERN, bond_name.upper()):
            continue

        isin = normalized_bond_name_to_isin.get(_normalize_bond_name(bond_name))
        if not isin:
            raise StatementPdfError(
                f"Could not identify fixed-income security {bond_name} from the PDF in Bond Master records."
            )

        try:
            market_price = Decimal(match.group("market_price").replace(",", ""))
            reported_quantity = Decimal(match.group("reported_quantity").replace(",", ""))
            market_value = Decimal(match.group("market_value").replace(",", ""))
        except InvalidOperation as error:
            raise StatementPdfError(
                f"The PDF contains invalid fixed-income values for {bond_name}."
            ) from error

        if not market_price.is_finite() or market_price <= 0:
            raise StatementPdfError(f"The PDF market price for ISIN {isin} must be greater than zero.")
        if not reported_quantity.is_finite() or reported_quantity < 0:
            raise StatementPdfError(f"The PDF reported quantity for ISIN {isin} must be zero or greater.")
        if not market_value.is_finite() or market_value < 0:
            raise StatementPdfError(f"The PDF market value for ISIN {isin} must be zero or greater.")

        parsed_row = ParsedMarketPrice(
            isin=isin,
            market_price=market_price,
            reported_quantity=reported_quantity,
            quantity_is_face_value=_legacy_quantity_is_monetary_nominal(
                reported_quantity,
                market_price,
                market_value,
            ),
        )
        existing_row = rows_by_isin.get(isin)
        if existing_row and existing_row.market_price != market_price:
            raise StatementPdfError(f"The PDF contains conflicting market prices for ISIN {isin}.")
        if existing_row and (
            existing_row.reported_quantity != reported_quantity
            or existing_row.quantity_is_face_value != parsed_row.quantity_is_face_value
        ):
            raise StatementPdfError(f"The PDF contains conflicting reported quantities for ISIN {isin}.")
        rows_by_isin[isin] = parsed_row

    return tuple(rows_by_isin.values())


def parse_statement_exchange_rates(text: str) -> tuple[ParsedExchangeRate, ...]:
    """Extract dated currency-pair rates from the statement's exchange table."""
    rows_by_pair: dict[tuple[str, str], ParsedExchangeRate] = {}
    for match in CURRENCY_RATE_PATTERN.finditer(text or ""):
        from_currency = match.group("from_currency").upper()
        to_currency = match.group("to_currency").upper()
        try:
            rate = Decimal(match.group("rate").replace(",", ""))
        except InvalidOperation as error:
            raise StatementPdfError(
                f"The PDF contains an invalid exchange rate for {from_currency} / {to_currency}."
            ) from error

        if not rate.is_finite() or rate <= 0:
            raise StatementPdfError(
                f"The PDF exchange rate for {from_currency} / {to_currency} must be greater than zero."
            )

        row = ParsedExchangeRate(from_currency, to_currency, rate)
        key = (from_currency, to_currency)
        existing_row = rows_by_pair.get(key)
        if existing_row and existing_row.rate != rate:
            raise StatementPdfError(
                f"The PDF contains conflicting exchange rates for {from_currency} / {to_currency}."
            )
        rows_by_pair[key] = row

    return tuple(rows_by_pair.values())


def _legacy_quantity_is_monetary_nominal(
    reported_quantity: Decimal,
    market_price: Decimal,
    market_value: Decimal,
) -> bool:
    """Distinguish monetary nominal from unit counts in legacy Face Value columns."""
    nominal_market_value = reported_quantity * market_price / Decimal("100")
    unit_market_value = reported_quantity * market_price
    nominal_distance = abs(market_value - nominal_market_value)
    unit_distance = abs(market_value - unit_market_value)
    if nominal_distance == unit_distance:
        raise StatementPdfError(
            "The PDF contains an ambiguous legacy quantity; the market value matches neither "
            "nominal nor unit interpretation more closely."
        )
    return nominal_distance < unit_distance


def extract_statement_pdf(
    content: bytes,
    passwords: list[str],
    *,
    account_no_hint: str | None = None,
    bond_name_to_isin: Mapping[str, str] | None = None,
) -> ParsedStatementPdf:
    """Decrypt a PDF with configured portfolio passwords and parse its first page."""
    if len(content) > MAX_STATEMENT_PDF_BYTES:
        raise StatementPdfError("The statement PDF must be 10 MB or smaller.")
    if b"%PDF-" not in content[:1024]:
        raise StatementPdfError("The attachment is not a valid PDF file.")

    try:
        probe = PdfReader(BytesIO(content), strict=False)
    except (PdfReadError, PdfStreamError, ValueError) as error:
        raise StatementPdfError("The attachment could not be read as a PDF.") from error

    if not probe.is_encrypted:
        return _parse_reader(probe, account_no_hint, bond_name_to_isin)

    for password in dict.fromkeys(password for password in passwords if password):
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if not reader.decrypt(password):
                continue
        except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError, ValueError):
            continue

        parsed = _parse_reader(reader, account_no_hint, bond_name_to_isin)
        return ParsedStatementPdf(
            account_no=parsed.account_no,
            statement_date=parsed.statement_date,
            market_prices=parsed.market_prices,
            exchange_rates=parsed.exchange_rates,
            unlock_password=password,
        )

    raise StatementPdfPasswordError(
        "The PDF could not be unlocked with any configured Bond Portfolio password."
    )


def get_statement_attachment_details(
    attachment: str,
    portfolio_name_hint: str | None = None,
) -> StatementAttachmentDetails:
    """Read an attached private PDF and resolve it to a visible portfolio."""
    portfolio_name_hint = optional_string(portfolio_name_hint, "Portfolio Name")
    content, original_filename = _read_private_attachment(attachment)
    credentials = _get_portfolio_credentials()
    bond_name_to_isin = _get_bond_name_to_isin()

    hinted_portfolios = [
        credential for credential in credentials if credential.portfolio_name == portfolio_name_hint
    ]
    if portfolio_name_hint and not hinted_portfolios:
        frappe.throw(f"No accessible Bond Portfolio exists for the selected portfolio {portfolio_name_hint}.")
    hinted_portfolio = hinted_portfolios[0] if hinted_portfolios else None

    try:
        parsed = extract_statement_pdf(
            content,
            [credential.password for credential in credentials if credential.password],
            account_no_hint=(
                _get_filename_account_hint(original_filename)
                or (normalize_account_number(hinted_portfolio.account_no) if hinted_portfolio else None)
            ),
            bond_name_to_isin=bond_name_to_isin,
        )
    except StatementPdfError as error:
        frappe.throw(str(error))

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
            "then attach the statement again."
        )
    if len(matching) > 1:
        frappe.throw(
            f"More than one Bond Portfolio uses account number {parsed.account_no}. "
            "Account No and Transaction Account No values must identify only one portfolio."
        )

    portfolio = matching[0]
    if hinted_portfolio and portfolio.portfolio_name != hinted_portfolio.portfolio_name:
        frappe.throw(
            f"The attached PDF belongs to Bond Portfolio {portfolio.portfolio_name}, "
            f"not the selected portfolio {hinted_portfolio.portfolio_name}."
        )
    if parsed.unlock_password is not None and (
        not portfolio.password or not hmac.compare_digest(portfolio.password, parsed.unlock_password)
    ):
        frappe.throw(
            f"The configured statement PDF password for portfolio {portfolio.portfolio_name} "
            "does not unlock this attachment."
        )

    return StatementAttachmentDetails(
        portfolio_name=portfolio.portfolio_name,
        account_no=parsed.account_no,
        portfolio_account_no=portfolio.account_no,
        statement_date=parsed.statement_date,
        market_prices=parsed.market_prices,
        exchange_rates=parsed.exchange_rates,
    )


def normalize_account_number(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _parse_reader(
    reader: PdfReader,
    account_no_hint: str | None,
    bond_name_to_isin: Mapping[str, str] | None,
) -> ParsedStatementPdf:
    if not reader.pages:
        raise StatementPdfError("The statement PDF has no pages.")

    page_texts = []
    try:
        for page in reader.pages:
            page_texts.append(page.extract_text() or "")
    except (DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError) as error:
        raise StatementPdfError("The statement PDF pages could not be read.") from error

    all_text = "\n".join(page_texts)
    parsed = parse_statement_pdf_text(page_texts[0], account_no_hint)
    return ParsedStatementPdf(
        account_no=parsed.account_no,
        statement_date=parsed.statement_date,
        market_prices=parse_statement_market_prices(all_text, bond_name_to_isin),
        exchange_rates=parse_statement_exchange_rates(all_text),
    )


def _read_private_attachment(attachment: str) -> tuple[bytes, str]:
    if not attachment:
        frappe.throw(_("Attach a PDF statement before saving."))
    if not attachment.lower().endswith(".pdf"):
        frappe.throw(_("Bond Statement attachments must be PDF files."))

    files = frappe.qb.get_query(
        "File",
        fields=["name"],
        filters={"file_url": attachment},
        order_by="creation desc",
        limit=1,
        ignore_permissions=False,
    ).run(pluck=True)
    if not files:
        frappe.throw(_("The attached PDF was not found or you do not have permission to read it."))

    file_doc = frappe.get_doc("File", files[0])
    file_doc.check_permission("read")
    if not file_doc.is_private:
        frappe.throw(_("Bond Statement PDFs must be uploaded as private files."))

    file_path = Path(file_doc.get_full_path()).resolve()
    private_files_path = Path(frappe.get_site_path("private", "files")).resolve()
    if not file_path.is_relative_to(private_files_path) or not file_path.is_file():
        frappe.throw(_("The attached private PDF could not be found."))
    if file_path.stat().st_size > MAX_STATEMENT_PDF_BYTES:
        frappe.throw(_("The statement PDF must be 10 MB or smaller."))

    return file_path.read_bytes(), file_doc.file_name


def _get_filename_account_hint(filename: str) -> str | None:
    match = ACCOUNT_FILENAME_PATTERN.search(filename or "")
    return normalize_account_number(match.group("account_no")) if match else None


def _get_bond_name_to_isin() -> dict[str, str]:
    """Return only unambiguous visible Bond Master name aliases."""
    aliases: defaultdict[str, set[str]] = defaultdict(set)
    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=["name", "bond_name"],
        ignore_permissions=False,
    ).run(as_dict=True)
    for bond in bonds:
        for alias in _bond_name_aliases(bond.bond_name):
            aliases[alias].add(bond.name)

    return {alias: next(iter(isins)) for alias, isins in aliases.items() if len(isins) == 1}


def _bond_name_aliases(value: str) -> set[str]:
    normalized = _normalize_bond_name(value)
    aliases = {normalized}
    for prefix in (
        "KENYA TREASURY BOND",
        "KENYA INFRASTRUCTURE BOND",
        "REPUBLIC OF KENYA",
    ):
        normalized_prefix = _normalize_bond_name(prefix)
        if normalized.startswith(f"{normalized_prefix}-"):
            aliases.add(normalized.removeprefix(f"{normalized_prefix}-"))
    return aliases


def _normalize_bond_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", (value or "").upper()).strip("-")


def _get_portfolio_credentials() -> list[PortfolioPdfCredentials]:
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
            PortfolioPdfCredentials(
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


def _unique_matches(text, patterns, converter):
    values = []
    for pattern in patterns:
        for match in pattern.findall(text or ""):
            try:
                value = converter(match)
            except ValueError as error:
                raise StatementPdfError(f"The PDF contains an invalid statement date: {match}.") from error
            if value not in values:
                values.append(value)
    return values


def _parse_statement_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()
