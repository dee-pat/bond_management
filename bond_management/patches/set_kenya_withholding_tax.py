from decimal import Decimal

import frappe

KENYA_WITHHOLDING_TAX = {
    "KE5000009653": Decimal("10"),
    "KE6000001328": Decimal("10"),
}


def execute():
    """Backfill the known Kenya bonds that have withholding tax."""
    for isin, withholding_tax in KENYA_WITHHOLDING_TAX.items():
        if not frappe.db.exists("Bond Master", isin):
            continue

        current = frappe.db.get_value("Bond Master", isin, "withholding_tax")
        if current is not None and Decimal(str(current)) == withholding_tax:
            continue

        frappe.db.set_value(
            "Bond Master",
            isin,
            "withholding_tax",
            withholding_tax,
            update_modified=False,
        )
