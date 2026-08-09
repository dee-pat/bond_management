import frappe

from bond_management.bond_management.utils.financial import quantize_money, to_decimal


def execute(transaction_names=None):
    """Backfill the net transaction amount from stored settlement components."""
    filters = {"name": ["in", transaction_names]} if transaction_names is not None else None
    transactions = frappe.qb.get_query(
        "Bond Transaction",
        fields=["name", "settlement_amount", "commission_amount", "transaction_amount"],
        filters=filters,
        ignore_permissions=True,
    ).run(as_dict=True)

    for transaction in transactions:
        expected_amount = quantize_money(
            to_decimal(transaction.settlement_amount) - to_decimal(transaction.commission_amount)
        )
        if to_decimal(transaction.transaction_amount) == expected_amount:
            continue

        frappe.db.set_value(
            "Bond Transaction",
            transaction.name,
            "transaction_amount",
            expected_amount,
            update_modified=False,
        )
