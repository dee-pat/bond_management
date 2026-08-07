import frappe

REPORT_VERSION = "QuantityBasis-v8"


def execute(statement_names=None):
    """Recalculate status and reports with quantity-basis-aware legacy parsing."""
    if statement_names is None:
        statement_names = frappe.qb.get_query(
            "Bond Statement",
            fields=["name"],
            order_by="statement_date asc, name asc",
            ignore_permissions=True,
        ).run(pluck=True)

    for statement_name in statement_names:
        statement = frappe.get_doc("Bond Statement", statement_name)
        statement.flags.quantity_reconciliation_report_file_name = (
            f"Bond-Quantity-Reconciliation-{REPORT_VERSION}-{statement.name}.pdf"
        )
        statement.flags.suppress_quantity_reconciliation_message = True
        statement.save()
