"""Deterministic, administrative seed data for investor browser tests."""

import os
from decimal import Decimal
from io import BytesIO

import frappe
from frappe import _
from pypdf import PdfWriter

from bond_management.bond_management.utils.investor_permissions import INVESTOR_ROLE

DEFAULT_INVESTOR_EMAIL = "bond-investor-ui@example.com"
TEST_PORTFOLIO_NAME = "UI Test Portfolio"
TEST_ACCOUNT_NUMBER = "UI Test Account"
TEST_BOND_ISIN = "UI-TEST-BOND-001"
TEST_YIELD_BOND_ISIN = "-UI-TEST-YIELD-BOND-002"
TEST_YIELD_FROM_DATE = "2095-01-01"
TEST_YIELD_MIDDLE_DATE = "2095-01-02"
TEST_YIELD_TO_DATE = "2095-01-03"
TEST_EXCHANGE_RATE_DATE = "2025-01-03"
TEST_EXCHANGE_RATE_FROM_CURRENCY = "GBP"
TEST_EXCHANGE_RATE_VALUE = Decimal("1.25")
TEST_MARKET_DATE = "2025-01-02"
TEST_TRANSACTION_REFERENCE = "UI-TEST-TRANSACTION-001"
TEST_STATEMENT_DATE = "2025-12-31"
TEST_TRANSACTION_ATTACHMENT = "ui-test-transaction.pdf"
TEST_STATEMENT_ATTACHMENT = "ui-test-statement.pdf"
TEST_RECONCILIATION_REPORT = "ui-test-reconciliation-report.pdf"


def seed_investor_ui_browser_test_data() -> dict[str, str]:
    """Seed the browser fixture with credentials supplied by the test runner."""
    email = _require_environment_variable("FRAPPE_USER")
    password = _require_environment_variable("FRAPPE_PASSWORD")
    return seed_investor_ui_test_data(email=email, password=password)


def seed_investor_ui_test_data(
    email: str = DEFAULT_INVESTOR_EMAIL,
    password: str | None = None,
) -> dict[str, str]:
    """Create the investor fixture; an optional password is supplied by the caller."""
    if frappe.session.user != "Administrator":
        frappe.throw(_("This test-data helper requires Administrator access."), frappe.PermissionError)
    if not isinstance(email, str) or not email:
        raise TypeError("email must be a non-empty string")
    if password is not None and not isinstance(password, str):
        raise TypeError("password must be a string or None")

    portfolio = _ensure_portfolio()
    bond = _ensure_bond()
    yield_bond = _ensure_bond(
        TEST_YIELD_BOND_ISIN,
        bond_name="Investor UI Yield Test Bond",
        currency="KES",
    )
    market_date = _ensure_market_date(bond.name)
    _ensure_yield_comparison_history(bond.name, yield_bond.name)
    exchange_rate = _ensure_exchange_rate()
    transaction = _ensure_transaction(bond.name, portfolio.name)
    statement = _ensure_statement(portfolio.name)
    _ensure_pdf_attachment(transaction, TEST_TRANSACTION_ATTACHMENT)
    _ensure_pdf_attachment(statement, TEST_STATEMENT_ATTACHMENT)
    _ensure_pdf_attachment(
        statement,
        TEST_RECONCILIATION_REPORT,
        fieldname="quantity_reconciliation_report",
    )
    user = _ensure_user(email, password)
    _ensure_user_permission(email, portfolio.name)

    return {
        "user": user.name,
        "portfolio": portfolio.name,
        "bond": bond.name,
        "yield_bond": yield_bond.name,
        "market_date": market_date.name,
        "exchange_rate": exchange_rate.name,
        "transaction": transaction.name,
        "statement": statement.name,
    }


def _ensure_portfolio():
    if frappe.db.exists("Bond Portfolio", TEST_PORTFOLIO_NAME):
        return frappe.get_doc("Bond Portfolio", TEST_PORTFOLIO_NAME)

    # This helper is invoked by the test-site bootstrap as Administrator; the
    # bypass is limited to deterministic fixture creation, not application APIs.
    return frappe.get_doc(
        {
            "doctype": "Bond Portfolio",
            "portfolio_name": TEST_PORTFOLIO_NAME,
            "account_no": TEST_ACCOUNT_NUMBER,
        }
    ).insert(ignore_permissions=True)


def _ensure_bond(
    isin: str = TEST_BOND_ISIN,
    *,
    bond_name: str = "Investor UI Test Bond",
    currency: str = "USD",
):
    if frappe.db.exists("Bond Master", isin):
        return frappe.get_doc("Bond Master", isin)

    return frappe.get_doc(
        {
            "doctype": "Bond Master",
            "bond_name": bond_name,
            "isin": isin,
            "currency": currency,
            "face_value_per_unit": 100,
            "coupon_rate": 7,
            "coupon_frequency": "2",
            "issue_date": "2025-01-01",
            "maturity_date": "2027-01-01",
            "first_coupon_date": "2025-07-01",
            "day_count_convention": "30E/360",
            "bond_type": "Kenya Treasury Bond",
            "principal_schedule": [{"repayment_date": "2027-01-01", "principal_units": 100}],
        }
    ).insert(ignore_permissions=True)


def _ensure_transaction(bond_name: str, portfolio_name: str):
    if frappe.db.exists("Bond Transaction", TEST_TRANSACTION_REFERENCE):
        return frappe.get_doc("Bond Transaction", TEST_TRANSACTION_REFERENCE)

    return frappe.get_doc(
        {
            "doctype": "Bond Transaction",
            "transaction_reference": TEST_TRANSACTION_REFERENCE,
            "transaction_type": "Purchase",
            "portfolio_name": portfolio_name,
            "isin": bond_name,
            "trade_date": "2025-12-30",
            "settlement_date": "2025-12-31",
            "quantity_face_value": 10,
            "price": 105,
            "accrued_interest_paid": 1,
            "commission": "0.45",
        }
    ).insert(ignore_permissions=True)


def _ensure_market_date(bond_name: str):
    name = frappe.db.exists("Bond Market Date", {"date": TEST_MARKET_DATE})
    market_date = (
        frappe.get_doc("Bond Market Date", name)
        if name
        else frappe.get_doc(
            {
                "doctype": "Bond Market Date",
                "date": TEST_MARKET_DATE,
                "bond_market_prices": [],
            }
        )
    )
    if not any(row.isin == bond_name for row in market_date.bond_market_prices):
        market_date.append(
            "bond_market_prices",
            {"isin": bond_name, "market_price": Decimal("102.5"), "currency": "USD"},
        )
        if name:
            market_date.save(ignore_permissions=True)
        else:
            market_date.insert(ignore_permissions=True)
    return market_date


def _ensure_yield_comparison_history(primary_bond: str, yield_bond: str) -> None:
    history = {
        TEST_YIELD_FROM_DATE: (
            (primary_bond, "USD", "102.5", "7.0"),
            (yield_bond, "KES", "99.25", "9.125"),
        ),
        TEST_YIELD_MIDDLE_DATE: ((primary_bond, "USD", "102.5", "7.25"),),
        TEST_YIELD_TO_DATE: (
            (primary_bond, "USD", "102.5", "7.5"),
            (yield_bond, "KES", "100.75", "9.625"),
        ),
    }
    for market_date, values in history.items():
        _ensure_yield_market_date(market_date, values)


def _ensure_yield_market_date(market_date: str, values: tuple[tuple[str, str, str, str], ...]) -> None:
    name = frappe.db.exists("Bond Market Date", {"date": market_date})
    document = (
        frappe.get_doc("Bond Market Date", name)
        if name
        else frappe.get_doc(
            {
                "doctype": "Bond Market Date",
                "date": market_date,
                "bond_market_prices": [],
            }
        )
    )
    changed = False
    for isin, currency, market_price, _future_xirr in values:
        if not any(row.isin == isin for row in document.bond_market_prices):
            document.append(
                "bond_market_prices",
                {"isin": isin, "currency": currency, "market_price": Decimal(market_price)},
            )
            changed = True

    if changed:
        if name:
            document.save(ignore_permissions=True)
        else:
            document.insert(ignore_permissions=True)

    for isin, _currency, market_price, future_xirr in values:
        frappe.db.set_value(
            "Bond Market Prices",
            {"parent": document.name, "isin": isin},
            {
                "market_price": Decimal(market_price),
                "future_xirr": Decimal(future_xirr),
            },
            update_modified=False,
        )


def _ensure_exchange_rate():
    filters = {
        "rate_date": TEST_EXCHANGE_RATE_DATE,
        "from_currency": TEST_EXCHANGE_RATE_FROM_CURRENCY,
        "to_currency": "USD",
    }
    name = frappe.db.exists("Bond Exchange Rate", filters)
    if name:
        return frappe.get_doc("Bond Exchange Rate", name)

    return frappe.get_doc(
        {
            "doctype": "Bond Exchange Rate",
            **filters,
            "rate": TEST_EXCHANGE_RATE_VALUE,
        }
    ).insert(ignore_permissions=True)


def _ensure_statement(portfolio_name: str):
    name = frappe.db.exists(
        "Bond Statement",
        {"portfolio_name": portfolio_name, "statement_date": TEST_STATEMENT_DATE},
    )
    statement = (
        frappe.get_doc("Bond Statement", name)
        if name
        else frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": portfolio_name,
                "statement_date": TEST_STATEMENT_DATE,
                "attachment": (
                    f"/private/files/{frappe.generate_hash(length=10)}-{TEST_STATEMENT_ATTACHMENT}"
                ),
            }
        )
    )
    statement.market_price_posting = None
    statement.flags.ignore_statement_pdf = True
    if name:
        statement.save(ignore_permissions=True)
    else:
        statement.insert(ignore_permissions=True)
    frappe.db.set_value(
        "Bond Statement",
        statement.name,
        "reconciliation_status",
        "Matched",
        update_modified=False,
    )
    statement.reconciliation_status = "Matched"
    return statement


def _ensure_pdf_attachment(document, filename: str, *, fieldname: str = "attachment") -> str:
    file_name = frappe.db.exists(
        "File",
        {
            "attached_to_doctype": document.doctype,
            "attached_to_name": document.name,
            "attached_to_field": fieldname,
            "is_private": 1,
        },
    )
    if file_name:
        file_doc = frappe.get_doc("File", file_name)
    else:
        content = _build_fixture_pdf(f"{document.doctype} {document.name} {fieldname}")
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": filename,
                "content": content,
                "is_private": 1,
                "attached_to_doctype": document.doctype,
                "attached_to_name": document.name,
                "attached_to_field": fieldname,
            }
        ).insert(ignore_permissions=True)

    if document.get(fieldname) != file_doc.file_url:
        document.db_set(fieldname, file_doc.file_url, update_modified=False)
        document.set(fieldname, file_doc.file_url)
    return file_doc.file_url


def _build_fixture_pdf(label: str) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Subject": f"Investor UI fixture: {label}"})
    writer.write(output)
    return output.getvalue()


def _ensure_user(email: str, password: str | None):
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        if not frappe.db.exists("Has Role", {"parent": email, "role": INVESTOR_ROLE}):
            user.append("roles", {"role": INVESTOR_ROLE})
            user.save(ignore_permissions=True)
        if password is not None:
            user.new_password = password
            user.save(ignore_permissions=True)
        return user

    values = {
        "doctype": "User",
        "email": email,
        "first_name": "Bond Investor UI",
        "send_welcome_email": 0,
        "roles": [{"role": INVESTOR_ROLE}],
    }
    if password is not None:
        values["new_password"] = password

    return frappe.get_doc(values).insert(ignore_permissions=True)


def _ensure_user_permission(email: str, portfolio_name: str) -> None:
    if frappe.db.exists(
        "User Permission",
        {
            "user": email,
            "allow": "Bond Portfolio",
            "for_value": portfolio_name,
            "apply_to_all_doctypes": 1,
        },
    ):
        return

    frappe.get_doc(
        {
            "doctype": "User Permission",
            "user": email,
            "allow": "Bond Portfolio",
            "for_value": portfolio_name,
            "apply_to_all_doctypes": 1,
        }
    ).insert(ignore_permissions=True)


def _require_environment_variable(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be set for investor browser tests")
    return value
