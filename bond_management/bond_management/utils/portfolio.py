from frappe.utils import getdate

from bond_management.bond_management.utils.financial import to_decimal


def get_coupon_position_from_transactions(rows, coupon_date, coupon_per_unit):
    """Calculate coupon entitlement from already-fetched ledger rows."""
    coupon_date = getdate(coupon_date)
    coupon_per_unit = to_decimal(coupon_per_unit)
    position = to_decimal(0)
    for row in rows:
        quantity = to_decimal(row.get("quantity_face_value"))
        settlement_date = getdate(row.get("settlement_date"))

        if settlement_date < coupon_date:
            position += quantity if row.get("transaction_type") == "Purchase" else -quantity
        elif settlement_date == coupon_date and row.get("transaction_type") == "Purchase":
            full_coupon = coupon_per_unit * quantity
            if to_decimal(row.get("accrued_interest_paid")) >= full_coupon:
                position += quantity

    return position


def get_ledger_position_from_transactions(rows, statement_date):
    """Calculate an end-of-day ledger position without additional database reads."""
    statement_date = getdate(statement_date)
    position = to_decimal(0)
    for row in rows:
        if getdate(row.get("settlement_date")) > statement_date:
            continue
        if row.get("transaction_type") == "Purchase":
            position += to_decimal(row.get("quantity_face_value"))
        elif row.get("transaction_type") == "Sale":
            position -= to_decimal(row.get("quantity_face_value"))

    return position
