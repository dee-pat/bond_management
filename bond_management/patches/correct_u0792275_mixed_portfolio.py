import frappe

SOURCE_REFERENCE = "U0792275"
SECOND_REFERENCE = "U0792348"
TARGET_PORTFOLIO = "Dhanbai"


def execute():
    if not frappe.db.exists("Bond Transaction", SOURCE_REFERENCE):
        return

    source = frappe.get_doc("Bond Transaction", SOURCE_REFERENCE)
    if not source.attachment:
        return

    details = source._get_transaction_attachment_details()
    rows = {row.transaction_reference: row for row in details.transactions}
    if SOURCE_REFERENCE not in rows or SECOND_REFERENCE not in rows:
        return

    if source.portfolio_name != TARGET_PORTFOLIO or not source.attachment_portfolio_override:
        source.portfolio_name = TARGET_PORTFOLIO
        source.attachment_portfolio_override = 1
        source.flags.transaction_attachment_details = details
        source.flags.allow_attachment_portfolio_override = True
        source.save()

    if frappe.db.exists("Bond Transaction", SECOND_REFERENCE):
        return

    second_row = rows[SECOND_REFERENCE]
    transaction = frappe.get_doc(
        {
            "doctype": "Bond Transaction",
            "attachment": source.attachment,
            **source._attachment_row_values(second_row),
        }
    )
    transaction.flags.transaction_attachment_details = details
    transaction.insert()
