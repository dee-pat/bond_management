import frappe


LEDGER_INDEX = "bond_transaction_portfolio_isin_settlement"
REPORT_INDEX = "bond_transaction_portfolio_settlement_isin"
MARKET_DATE_UNIQUE = "unique_bond_market_date"


def execute():
    ensure_bond_query_indexes()


def ensure_bond_query_indexes():
    """Add indexes that enforce market dates and bound transaction locking."""
    duplicate_dates = frappe.qb.get_query(
        "Bond Market Date",
        fields=["date", {"COUNT": "name", "as": "snapshot_count"}],
        group_by="date",
        ignore_permissions=True,
    ).run(as_dict=True)
    duplicate_dates = [row.date for row in duplicate_dates if row.snapshot_count > 1]
    if duplicate_dates:
        dates = ", ".join(str(date) for date in duplicate_dates[:10])
        frappe.throw(
            "Cannot enforce one Bond Market Date per date because duplicates exist: "
            f"{dates}. Merge or remove the duplicate snapshots, then run migrate again."
        )

    frappe.db.add_index(
        "Bond Transaction",
        ["portfolio_name", "isin", "settlement_date"],
        index_name=LEDGER_INDEX,
    )
    frappe.db.add_index(
        "Bond Transaction",
        ["portfolio_name", "settlement_date", "isin"],
        index_name=REPORT_INDEX,
    )
    frappe.db.add_unique(
        "Bond Market Date",
        ["date"],
        constraint_name=MARKET_DATE_UNIQUE,
    )
