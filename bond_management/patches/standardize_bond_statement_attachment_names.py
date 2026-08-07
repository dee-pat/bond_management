import frappe

from bond_management.bond_management.utils.statement_attachment import (
    standardize_statement_attachment,
)
from bond_management.bond_management.utils.statement_pdf import (
    get_statement_attachment_details,
)


def execute(statement_names=None):
    """Backfill canonical private filenames for existing Bond Statement PDFs."""
    if statement_names is None:
        statement_names = frappe.qb.get_query(
            "Bond Statement",
            fields=["name"],
            order_by="statement_date asc",
            ignore_permissions=False,
        ).run(pluck=True)

    for statement_name in statement_names:
        statement = frappe.get_doc("Bond Statement", statement_name)
        details = get_statement_attachment_details(statement.attachment, statement.portfolio_name)
        old_attachment = statement.attachment
        new_attachment = standardize_statement_attachment(
            statement,
            details.portfolio_account_no,
            details.statement_date,
        )
        if new_attachment != old_attachment:
            statement.db_set("attachment", new_attachment, update_modified=False)
