from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

from frappe.utils import getdate
from frappe.utils.data import DateTimeLikeObject

from bond_management.bond_management.utils.financial import DecimalInput, to_decimal


def get_coupon_position_from_transactions(
    rows: Iterable[Mapping[str, Any]], coupon_date: DateTimeLikeObject, coupon_per_unit: DecimalInput
) -> Decimal:
    """Return the face quantity entitled to the coupon on ``coupon_date`` from fetched ledger rows.

    Settlements before the coupon date count, sales negatively. A same-day
    purchase counts only when its accrued interest paid covers the full coupon.
    """
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


def get_ledger_position_from_transactions(
    rows: Iterable[Mapping[str, Any]], statement_date: DateTimeLikeObject
) -> Decimal:
    """Return the end-of-day face quantity held on ``statement_date``, effective on settlement date."""
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
