import frappe

LEDGER_INDEX = "bond_transaction_portfolio_isin_settlement"
REPORT_INDEX = "bond_transaction_portfolio_settlement_isin"
MARKET_DATE_UNIQUE = "unique_bond_market_date"
STATEMENT_ATTACHMENT_UNIQUE = "unique_bond_statement_attachment"
EXCHANGE_RATE_UNIQUE = "unique_bond_exchange_rate"


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

    duplicate_attachments = frappe.qb.get_query(
        "Bond Statement",
        fields=["attachment", {"COUNT": "name", "as": "statement_count"}],
        group_by="attachment",
        ignore_permissions=True,
    ).run(as_dict=True)
    duplicate_attachments = [
        row.attachment for row in duplicate_attachments if row.attachment and row.statement_count > 1
    ]
    if duplicate_attachments:
        attachments = ", ".join(duplicate_attachments[:10])
        frappe.throw(
            "Cannot enforce one Bond Statement per attachment because duplicates exist: "
            f"{attachments}. Run the duplicate cleanup patch, then migrate again."
        )

    duplicate_exchange_rates = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=[
            "rate_date",
            "from_currency",
            "to_currency",
            {"COUNT": "name", "as": "rate_count"},
        ],
        group_by="rate_date, from_currency, to_currency",
        ignore_permissions=True,
    ).run(as_dict=True)
    duplicate_exchange_rates = [row for row in duplicate_exchange_rates if row.rate_count > 1]
    if duplicate_exchange_rates:
        duplicates = ", ".join(
            f"{row.rate_date}/{row.from_currency}/{row.to_currency}" for row in duplicate_exchange_rates[:10]
        )
        frappe.throw(
            "Cannot enforce one Bond Exchange Rate per date/currency pair because "
            f"duplicates exist: {duplicates}. Merge or remove the duplicate rows, then run migrate again."
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
    frappe.db.add_unique(
        "Bond Statement",
        ["attachment"],
        constraint_name=STATEMENT_ATTACHMENT_UNIQUE,
    )
    frappe.db.add_unique(
        "Bond Exchange Rate",
        ["rate_date", "from_currency", "to_currency"],
        constraint_name=EXCHANGE_RATE_UNIQUE,
    )
