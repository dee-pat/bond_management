import frappe

from bond_management.bond_management.doctype.bond_transaction.bond_transaction import (
    calculate_transaction_principal_value,
)
from bond_management.bond_management.utils.financial import quantize_money, to_decimal


def execute(transaction_names=None):
    """Backfill transaction consideration after Principal became price-adjusted."""
    filters = {"name": ["in", transaction_names]} if transaction_names is not None else None
    transactions = frappe.qb.get_query(
        "Bond Transaction",
        fields=["name", "face_value_per_unit", "quantity_face_value", "price", "principal"],
        filters=filters,
        ignore_permissions=True,
    ).run(as_dict=True)

    for transaction in transactions:
        expected_principal = quantize_money(
            calculate_transaction_principal_value(
                transaction.face_value_per_unit,
                transaction.quantity_face_value,
                transaction.price,
            )
        )
        if to_decimal(transaction.principal) == expected_principal:
            continue

        # Principal is a derived transaction snapshot. Updating only this field
        # preserves the already-recorded settlement and accrued-interest values.
        frappe.db.set_value(
            "Bond Transaction",
            transaction.name,
            "principal",
            expected_principal,
            update_modified=False,
        )
