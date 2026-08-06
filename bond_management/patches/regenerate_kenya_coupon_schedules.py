import frappe

from bond_management.bond_management.utils.coupon_schedule import (
    is_kenya_day_count_convention,
)


def execute(bond_names=None):
    """Regenerate maturity-anchored Kenya schedules and their derived first coupon."""
    filters = {"name": ["in", bond_names]} if bond_names is not None else None
    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=["name", "day_count_convention"],
        filters=filters,
        ignore_permissions=True,
    ).run(as_dict=True)

    for row in bonds:
        if not is_kenya_day_count_convention(row.day_count_convention):
            continue

        bond = frappe.get_doc("Bond Master", row.name)
        # A migration is the administrative service boundary. Saving runs the
        # same financial validations used for interactive edits and fails rather
        # than guessing when a legacy repayment is off the 182-day cadence.
        bond.save(ignore_permissions=True)
