"""Representative legacy rows for the opt-in disposable migration lifecycle."""

import frappe
from frappe.database.utils import drop_index_if_exists

from bond_management.bond_management.tests.factories import (
    make_bond,
    make_exchange_rate,
    make_market_date,
    make_portfolio,
    make_statement,
    make_transaction,
)
from bond_management.bond_management.tests.pdf_factory import make_text_pdf
from bond_management.patches.add_bond_query_indexes import (
    EXCHANGE_RATE_UNIQUE,
    STATEMENT_ATTACHMENT_UNIQUE,
)

USD_ISIN = "US0000000991"
KENYA_ISIN = "KE0000000992"
ACCOUNT = "MIGRATION-ACCOUNT"
TRANSACTION = "MIGRATION-PURCHASE"
PASSWORD = "synthetic-lifecycle-password"


def prepare_legacy_rows():
    """Called only after the lifecycle helper checks its administrative boundary."""
    from bond_management.bond_management.tests.migration_lifecycle import _guard

    _guard()
    if frappe.db.exists("Bond Master", USD_ISIN):
        raise RuntimeError("Lifecycle fixtures already exist; use a new disposable bench.")
    portfolio = make_portfolio(
        portfolio_name="Migration Lifecycle Portfolio",
        account_no=ACCOUNT,
        statement_pdf_password=PASSWORD,
    )
    usd = make_bond(isin=USD_ISIN, bond_name="Migration USD Bond")
    kenya = make_bond(
        isin=KENYA_ISIN,
        bond_name="Migration Kenya Bond",
        currency="KES",
        issue_date="2025-01-01",
        day_count_convention="Actual/364(Kenya)",
        first_coupon_date="2025-01-03",
    )
    confirmation = _private_pdf("legacy-confirmation.pdf", _confirmation_text())
    transaction = make_transaction(usd, portfolio, transaction_reference=TRANSACTION)
    _attach_file(confirmation, transaction)
    frappe.db.set_value(
        "Bond Transaction",
        transaction.name,
        {"attachment": confirmation.file_url, "principal": "1000", "transaction_amount": "999"},
        update_modified=False,
    )
    statement, duplicate, statement_file = _legacy_statement(portfolio, usd)
    market = make_market_date(kenya, market_price="98", date="2025-12-29")
    _stale_kenya_values(kenya, market)
    exchange_rate = _legacy_exchange_rate(portfolio, statement)
    return {
        "portfolio": portfolio.name,
        "transaction": transaction.name,
        "statement": statement.name,
        "duplicate": duplicate.name,
        "statement_file": statement_file.name,
        "confirmation_file": confirmation.name,
        "market_date": market.name,
        "exchange_rate": exchange_rate.name,
    }


def _legacy_statement(portfolio, usd):
    statement_file = _private_pdf(
        "legacy-statement.pdf",
        f"SUMMARY OF ACCOUNT As of 31/12/2025 IS Account: {ACCOUNT}\n"
        f"{USD_ISIN}\nUSD 1,000.00 99.000000 7.000000 101.250000 990.00 1,012.50 01/01/2027\nKES / USD 0.008",
    )
    statement = make_statement(
        portfolio,
        insert=False,
        attachment=statement_file.file_url,
        bond_statement_details=[
            {
                "isin": usd.name,
                "quantity": 10,
                "principal_factor": "1",
                "market_price": "101.25",
                "currency": "USD",
            }
        ],
    )
    # Import without current hooks so registered patches must rename the legacy
    # PDF and generate the reconciliation report themselves.
    statement.name = "MIGRATION-STATEMENT"
    statement.db_insert()
    for child in statement.bond_statement_details:
        child.parent = statement.name
        child.db_insert()
    statement_file.reload()
    _attach_file(statement_file, statement)
    # This deliberately bypasses today's validation/index to reproduce old rows.
    drop_index_if_exists("tabBond Statement", STATEMENT_ATTACHMENT_UNIQUE)
    duplicate = frappe.copy_doc(statement)
    duplicate.name = "MIGRATION-DUPLICATE-STATEMENT"
    duplicate.docstatus = 0
    duplicate.creation = "2026-01-02 00:00:00"
    duplicate.db_insert()
    for child in duplicate.bond_statement_details:
        child.parent = duplicate.name
        child.docstatus = 0
        child.db_insert()
    frappe.db.set_value(
        "Bond Statement", statement.name, "creation", "2026-01-01 00:00:00", update_modified=False
    )
    shared_file = frappe.copy_doc(statement_file)
    shared_file.update({"attached_to_name": duplicate.name, "folder": None})
    shared_file.flags.copy_from_existing_file = True
    shared_file.insert()
    frappe.db.set_value(
        "Bond Statement", statement.name, "reconciliation_status", "Unchecked", update_modified=False
    )
    return statement, duplicate, statement_file


def _stale_kenya_values(kenya, market):
    frappe.db.set_value(
        "Bond Master",
        kenya.name,
        {"quantity_change": 0, "first_coupon_date": "2025-01-01"},
        update_modified=False,
    )
    frappe.db.set_value(
        "Bond Coupon Schedule",
        kenya.coupon_schedule[0].name,
        "coupon_date",
        "2025-01-01",
        update_modified=False,
    )
    frappe.db.set_value(
        "Bond Market Prices",
        market.bond_market_prices[0].name,
        {
            "principal_factor": "0.5",
            "future_xirr": "-999",
            "weighted_avg_repayment_date": "2026-01-01",
            "weighted_avg_repayment_years": "0",
            "maturity_date": "2026-01-01",
        },
        update_modified=False,
    )


def _legacy_exchange_rate(portfolio, statement):
    rate = make_exchange_rate(rate_date="2025-12-31", rate="0.008")
    frappe.db.set_value(
        "Bond Exchange Rate",
        rate.name,
        {"statement": statement.name, "source": "Statement", "reverse_rate": "0", "manual_fallback": 0},
        update_modified=False,
    )
    # Recreate the obsolete schema only in the guarded disposable database.
    frappe.db.sql_ddl("ALTER TABLE `tabBond Exchange Rate` ADD COLUMN `portfolio_name` varchar(140)")
    frappe.db.set_value(
        "Bond Exchange Rate", rate.name, "portfolio_name", portfolio.name, update_modified=False
    )
    drop_index_if_exists("tabBond Exchange Rate", EXCHANGE_RATE_UNIQUE)
    frappe.db.add_unique(
        "Bond Exchange Rate",
        ["portfolio_name", "rate_date", "from_currency", "to_currency"],
        constraint_name=EXCHANGE_RATE_UNIQUE,
    )
    return rate


def _private_pdf(filename, text):
    return frappe.get_doc(
        {"doctype": "File", "file_name": filename, "content": make_text_pdf(text, PASSWORD), "is_private": 1}
    ).insert()


def _attach_file(file_doc, document):
    file_doc.update(
        {
            "attached_to_doctype": document.doctype,
            "attached_to_name": document.name,
            "attached_to_field": "attachment",
        }
    )
    file_doc.save()


def _confirmation_text():
    return f"""Account No : {ACCOUNT}
TRANSACTION DETAILS:
Purchase
Bonds Name : Migration USD Bond - {USD_ISIN}
ISIN : {USD_ISIN}
Currency : USD Quantity : 10.000000
Price : 105.000000 Face Value : 1,000.00 Principal : 1,050.00
Trade Date : 30/12/2025 Settlement Amount in Currency : 1,051.00
Settlement Date : 31/12/2025 Commission % : 2%
Accrued Interest : 1.00 Commission Amount : 20.00
Transaction Reference : {TRANSACTION}
"""
