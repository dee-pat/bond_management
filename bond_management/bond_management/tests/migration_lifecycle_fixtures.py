"""Representative legacy rows for the opt-in temporary-site migration lifecycle.

Only invariants that registered patches still own are seeded here: statement
exchange rates without provenance rows, manual rates without their flag, and
financial shares created before decision 0012.
"""

import frappe

from bond_management.bond_management.tests.factories import (
    make_bond,
    make_exchange_rate,
    make_portfolio,
    make_private_file,
    make_statement,
    make_transaction,
    make_user,
    unique_name,
)

USD_ISIN = "US0000000991"
TRANSACTION = "MIGRATION-PURCHASE"


def prepare_legacy_rows():
    """Called only after the lifecycle helper checks its administrative boundary."""
    from bond_management.bond_management.tests.migration_lifecycle import _guard

    _guard()
    if frappe.db.exists("Bond Master", USD_ISIN):
        raise RuntimeError("Lifecycle fixtures already exist; use a new temporary lifecycle site.")
    portfolio = make_portfolio(portfolio_name="Migration Lifecycle Portfolio")
    usd = make_bond(isin=USD_ISIN, bond_name="Migration USD Bond")
    transaction = make_transaction(usd, portfolio, transaction_reference=TRANSACTION)
    statement = make_statement(portfolio)
    statement_rate = make_exchange_rate(rate_date="2025-12-31", rate="0.008")
    manual_rate = make_exchange_rate(rate_date="2025-12-30", rate="0.0079")
    # Reproduce rows written before provenance existed; the bypass is limited
    # to the guarded disposable database.
    frappe.db.delete(
        "Bond Exchange Rate Source", {"exchange_rate": ["in", [statement_rate.name, manual_rate.name]]}
    )
    frappe.db.set_value(
        "Bond Exchange Rate",
        statement_rate.name,
        {"statement": statement.name, "source": "Statement", "manual_fallback": 0},
        update_modified=False,
    )
    frappe.db.set_value("Bond Exchange Rate", manual_rate.name, "manual_fallback", 0, update_modified=False)
    return {
        "portfolio": portfolio.name,
        "transaction": transaction.name,
        "statement": statement.name,
        "exchange_rate": statement_rate.name,
        "manual_exchange_rate": manual_rate.name,
        "shares": _prepare_legacy_shares(portfolio),
    }


def _prepare_legacy_shares(portfolio):
    user = make_user()
    financial_file = make_private_file(portfolio.doctype, portfolio.name)
    unrelated_file = make_private_file("User", user.name)
    removed = [
        _legacy_share(portfolio, user.name),
        _legacy_share(portfolio, everyone=1),
        _legacy_share(financial_file, user.name),
    ]
    kept = [_legacy_share(user, user.name), _legacy_share(unrelated_file, user.name)]
    fields = ("name", "share_doctype", "share_name", "user", "everyone", "read", "write")
    return {
        "removed": [share.name for share in removed],
        "kept": [{field: share.get(field) for field in fields} for share in kept],
        "files": [
            {
                "name": file.name,
                "attached_to_doctype": file.attached_to_doctype,
                "attached_to_name": file.attached_to_name,
                "file_url": file.file_url,
                "is_private": file.is_private,
                "content": frappe.get_doc("File", file.name).get_content(),
            }
            for file in (financial_file, unrelated_file)
        ],
    }


def _legacy_share(document, user=None, *, everyone=0):
    # prepare_legacy_rows enforces the temporary-site guard. Only direct insertion
    # can reproduce grants that today's financial-share hooks correctly reject.
    share = frappe.get_doc(
        {
            "doctype": "DocShare",
            "name": unique_name("lifecycle-share"),
            "share_doctype": document.doctype,
            "share_name": document.name,
            "user": user,
            "everyone": everyone,
            "read": 1,
            "write": 0,
            "owner": "Administrator",
        }
    )
    share.db_insert()
    return share
