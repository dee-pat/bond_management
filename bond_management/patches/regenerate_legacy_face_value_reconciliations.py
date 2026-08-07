import frappe

from bond_management.bond_management.utils.statement_pdf import (
    get_statement_attachment_details,
)
from bond_management.bond_management.utils.statement_quantity_reconciliation import (
    reconcile_statement_quantities,
)
from bond_management.bond_management.utils.statement_quantity_report import (
    attach_quantity_reconciliation_report,
)

REPORT_VERSION = "FaceValue-v2"


def execute(statement_names=None):
    """Regenerate reports where the older PDF stores nominal Face Value."""
    if statement_names is None:
        statement_names = frappe.qb.get_query(
            "Bond Statement",
            fields=["name"],
            order_by="statement_date asc, name asc",
            ignore_permissions=True,
        ).run(pluck=True)

    for statement_name in statement_names:
        statement = frappe.get_doc("Bond Statement", statement_name)
        file_name = f"Bond-Quantity-Reconciliation-{REPORT_VERSION}-{statement.name}.pdf"
        existing = frappe.qb.get_query(
            "File",
            fields=["file_url"],
            filters={
                "file_name": file_name,
                "attached_to_doctype": "Bond Statement",
                "attached_to_name": statement.name,
                "attached_to_field": "quantity_reconciliation_report",
            },
            limit=1,
            ignore_permissions=True,
        ).run(pluck=True)
        if existing:
            if statement.quantity_reconciliation_report != existing[0]:
                statement.db_set(
                    "quantity_reconciliation_report",
                    existing[0],
                    update_modified=False,
                )
            continue

        details = get_statement_attachment_details(statement.attachment, statement.portfolio_name)
        if not any(row.quantity_is_face_value for row in details.market_prices):
            continue

        comparisons = reconcile_statement_quantities(
            details.market_prices,
            statement.bond_statement_details,
        )
        report_url = attach_quantity_reconciliation_report(
            statement,
            comparisons,
            file_name=file_name,
        )
        statement.db_set(
            "quantity_reconciliation_report",
            report_url,
            update_modified=False,
        )
