
from frappe.utils import getdate


def get_coupon_period(coupon_schedule, settlement_date):
    settlement_date = getdate(settlement_date)

    if not coupon_schedule or not settlement_date:
        return None
    period = None
    for row in coupon_schedule:
        start = getdate(row.get("period_start"))
        end   = getdate(row.get("period_end"))
        if start and end:
            if start <= settlement_date <= end:
                period = row
                break

    return period


def days_30E_360(start, end):
    d1 = min(start.day, 30)
    d2 = min(end.day, 30)

    return (
        (end.year - start.year) * 360 +
        (end.month - start.month) * 30 +
        (d2 - d1)
    )


def calculate_accrued_fraction(
    coupon_schedule,
    settlement_date,
    day_count_convention,
    face_value_per_unit,
    coupon_frequency,
    coupon_rate
):
    period = get_coupon_period(coupon_schedule, settlement_date)

    if not period:
        return 0

    start = getdate(period.get("period_start"))
    end   = getdate(period.get("period_end"))
    settlement = getdate(settlement_date)

    # Day count
    if day_count_convention == "30E/360":
        accrued_days = days_30E_360(start, settlement)
        total_days = 360
        # total_days = days_30E_360(start, end) * coupon_frequency
    elif day_count_convention == "ACT/ACT":
        accrued_days = (settlement - start).days
        total_days = (end - start).days  * int(coupon_frequency)
    elif day_count_convention == "ACT/364":
        accrued_days = (settlement - start).days
        total_days = 364
    elif day_count_convention == "ACT/365":
        accrued_days = (settlement - start).days
        total_days = 365
    else:
        raise ValueError(f"Unsupported day count convention: {day_count_convention}")

    if total_days == 0:
        return 0

    fraction = accrued_days / total_days

    return coupon_rate / 100 * face_value_per_unit * fraction


import frappe

@frappe.whitelist()
def get_accrued_interest(isin=None, settlement_date=None, quantity_face_value=None):

    if not isin or not settlement_date or not quantity_face_value:
        return 0

    settlement_date = getdate(settlement_date)
    quantity_face_value = float(quantity_face_value)

    bond_doc = frappe.get_doc("Bond Master", isin)

    # convert only once
    schedule = [row.as_dict() for row in bond_doc.coupon_schedule]

    fraction = calculate_accrued_fraction(
        schedule,
        settlement_date,
        bond_doc.day_count_convention,
        bond_doc.face_value_per_unit,
        bond_doc.coupon_frequency,
        bond_doc.coupon_rate 
    )

    return fraction * quantity_face_value
