import frappe

from bond_management.bond_management.utils.transaction_pdf import (
    get_transaction_attachment_details,
    transaction_attachment_row_values,
)

SOURCE_REFERENCE = "U0792275"
SECOND_REFERENCE = "U0792348"
TARGET_PORTFOLIO = "Dhanbai"


def execute():
    if not frappe.db.exists("Bond Transaction", SOURCE_REFERENCE):
        return

    source = frappe.get_doc("Bond Transaction", SOURCE_REFERENCE)
    if not source.attachment:
        return

    details = get_transaction_attachment_details(source.attachment)
    rows = {row.transaction_reference: row for row in details.transactions}
    if SOURCE_REFERENCE not in rows or SECOND_REFERENCE not in rows:
        return

    if source.portfolio_name != TARGET_PORTFOLIO or not source.attachment_portfolio_override:
        # The patch owns this correction. Update only the two affected fields;
        # invoking the private controller validation would recalculate unrelated
        # legacy financial values.
        frappe.db.set_value(
            "Bond Transaction",
            SOURCE_REFERENCE,
            {
                "portfolio_name": TARGET_PORTFOLIO,
                "attachment_portfolio_override": 1,
            },
            update_modified=False,
        )

    if frappe.db.exists("Bond Transaction", SECOND_REFERENCE):
        return

    second_row = rows[SECOND_REFERENCE]
    transaction = frappe.get_doc(
        {
            "doctype": "Bond Transaction",
            "attachment": source.attachment,
            **transaction_attachment_row_values(second_row),
        }
    )
    transaction.flags.transaction_attachment_details = details
    transaction.insert()
