import frappe

from bond_management.bond_management.utils.accrual import is_quantity_change_bond


def execute():
    """Synchronize the derived Bond Master flag for existing records."""
    bonds = frappe.get_all(
        "Bond Master",
        fields=["name", "currency", "day_count_convention"],
        ignore_permissions=True,
    )
    for bond in bonds:
        expected = int(is_quantity_change_bond(bond))
        current = frappe.db.get_value("Bond Master", bond.name, "quantity_change")
        if current != expected:
            # This is a derived migration field; no financial schedule or
            # transaction data is changed by synchronizing it.
            frappe.db.set_value(
                "Bond Master",
                bond.name,
                "quantity_change",
                expected,
                update_modified=False,
            )
