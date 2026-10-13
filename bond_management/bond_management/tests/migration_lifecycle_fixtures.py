"""Representative legacy rows for the opt-in temporary-site migration lifecycle.

Only invariants that registered patches still own are seeded here: statement
exchange rates without provenance rows and manual rates without their flag.
"""

import frappe

from bond_management.bond_management.tests.factories import (
    make_bond,
    make_exchange_rate,
    make_portfolio,
    make_statement,
    make_transaction,
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
    }
