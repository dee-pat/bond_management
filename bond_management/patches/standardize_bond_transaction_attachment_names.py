from collections import defaultdict

import frappe

from bond_management.bond_management.utils.transaction_attachment import (
    standardize_transaction_attachment,
)


def execute(transaction_names=None):
    """Backfill canonical filenames for existing PDF-backed Bond Transactions."""
    filters = {"attachment": ["like", "%.pdf"]}
    if transaction_names is not None:
        filters["name"] = ["in", transaction_names]

    rows = frappe.qb.get_query(
        "Bond Transaction",
        fields=["name", "attachment", "settlement_date"],
        filters=filters,
        order_by="settlement_date asc, name asc",
        ignore_permissions=False,
    ).run(as_dict=True)
    rows_by_attachment = defaultdict(list)
    for row in rows:
        rows_by_attachment[row.attachment].append(row)

    for original_attachment, attachment_rows in rows_by_attachment.items():
        available_attachment = original_attachment
        for row in attachment_rows:
            transaction = frappe.get_doc("Bond Transaction", row.name)
            portfolio = frappe.get_doc("Bond Portfolio", transaction.portfolio_name)
            portfolio.check_permission("read")
            transaction.attachment = available_attachment
            new_attachment = standardize_transaction_attachment(
                transaction,
                portfolio.account_no,
                transaction.settlement_date,
            )
            if new_attachment != row.attachment:
                transaction.db_set("attachment", new_attachment, update_modified=False)
            available_attachment = new_attachment
