import frappe

from bond_management.bond_management.utils.coupon_schedule import (
    generate_coupon_schedule,
    is_kenya_day_count_convention,
)


def execute(bond_names=None):
    """Regenerate maturity-anchored Kenya schedules and their derived first coupon."""
    filters = {"name": ["in", bond_names]} if bond_names is not None else None
    bonds = frappe.qb.get_query(
        "Bond Master",
        fields=[
            "name",
            "issue_date",
            "maturity_date",
            "coupon_frequency",
            "coupon_rate",
            "first_coupon_date",
            "day_count_convention",
        ],
        filters=filters,
        ignore_permissions=True,
    ).run(as_dict=True)
    names = [row.name for row in bonds]
    principal_rows = (
        frappe.qb.get_query(
            "Bond Principal Schedule",
            fields=["parent", "repayment_date"],
            filters={
                "parent": ["in", names],
                "parenttype": "Bond Master",
                "parentfield": "principal_schedule",
            },
            ignore_permissions=True,
        ).run(as_dict=True)
        if names
        else []
    )
    principal_dates = {}
    for principal_row in principal_rows:
        principal_dates.setdefault(principal_row.parent, []).append(principal_row.repayment_date)

    for row in bonds:
        if not is_kenya_day_count_convention(row.day_count_convention):
            continue

        schedule = generate_coupon_schedule(
            row.issue_date,
            row.maturity_date,
            row.coupon_frequency,
            row.coupon_rate,
            row.first_coupon_date,
            row.day_count_convention,
            principal_dates=principal_dates.get(row.name, []),
        )
        # A migration is the administrative service boundary. Rebuild only the
        # derived child table and first-coupon value; do not invoke a private
        # controller save that can rewrite unrelated legacy fields.
        frappe.db.delete(
            "Bond Coupon Schedule",
            {
                "parent": row.name,
                "parenttype": "Bond Master",
                "parentfield": "coupon_schedule",
            },
        )
        for index, schedule_row in enumerate(schedule, start=1):
            frappe.get_doc(
                {
                    "doctype": "Bond Coupon Schedule",
                    "parent": row.name,
                    "parenttype": "Bond Master",
                    "parentfield": "coupon_schedule",
                    "idx": index,
                    **schedule_row,
                }
            ).db_insert()
        if schedule:
            frappe.db.set_value(
                "Bond Master",
                row.name,
                "first_coupon_date",
                schedule[0]["coupon_date"],
                update_modified=False,
            )
