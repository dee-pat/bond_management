from dateutil.relativedelta import relativedelta
import frappe
from frappe.utils import getdate, add_days
from frappe.utils.data import get_last_day

from bond_management.bond_management.utils.accrual import days_30E_360


def generate_coupon_schedule1(issue_date, maturity_date, coupon_frequency):

    issue_date = getdate(issue_date)
    maturity_date = getdate(maturity_date)

    if not issue_date or not maturity_date or not coupon_frequency:
        return []

    if issue_date >= maturity_date:
        raise ValueError("Issue date must be before maturity date")

    try:
        coupon_frequency = int(coupon_frequency)
    except ValueError:
        frappe.throw("Coupon Frequency must be a number")

    step = relativedelta(months=int(12 / int(coupon_frequency)))

    # Step 1: generate coupon dates backwards from maturity
    dates = []
    current = maturity_date
    eom = maturity_date.day == get_last_day(maturity_date)

    while current > issue_date:
        dates.append(current)
        current = current - step

        if eom:
            current = get_last_day(current)

    # Optional: include first stub if needed
    # Ensure first period starts at issue_date
    dates = sorted(dates)

    coupon_schedule = []
    prev = issue_date

    for d in dates:
        coupon_schedule.append(
            {
                "coupon_date": d,
                "period_start": prev,
                "period_end": add_days(
                    d, -1
                ),  # The period end is the day before the coupon date
            }
        )
        prev = d

    return coupon_schedule


def generate_coupon_schedule(
    issue_date,
    maturity_date,
    coupon_frequency,
    coupon_rate,
    first_coupon_date,
    day_count_convention,
):

    issue_date = getdate(issue_date)
    maturity_date = getdate(maturity_date)
    first_coupon_date = getdate(first_coupon_date) if first_coupon_date else None

    if not issue_date or not maturity_date or not coupon_frequency:
        return []

    if issue_date >= maturity_date:
        raise ValueError("Issue date must be before maturity date")

    try:
        coupon_frequency = int(coupon_frequency)
    except ValueError:
        frappe.throw("Coupon Frequency must be a number")

    step = relativedelta(months=int(12 / coupon_frequency))

    # Step 1: generate schedule backwards
    dates = []
    current = maturity_date
    eom = maturity_date.day == get_last_day(maturity_date)

    while current > issue_date:
        dates.append(current)
        current = current - step

        if eom:
            current = get_last_day(current)

    dates = sorted(dates)

    # Step 2: handle first coupon override (stub)
    if first_coupon_date:
        if first_coupon_date <= issue_date:
            frappe.throw("First Coupon Date must be after Issue Date")

        if first_coupon_date >= maturity_date:
            frappe.throw("First Coupon Date must be before Maturity Date")

        dates = [d for d in dates if d > first_coupon_date]
        dates.insert(0, first_coupon_date)

    # Step 3: build schedule with factor
    coupon_schedule = []
    prev = issue_date

    for d in dates:
        period_start = prev
        period_end = add_days(d, -1)

        # Day count
        if day_count_convention == "30E/360":
            accrued_days = days_30E_360(period_start, d)
            total_days = 360
            # total_days = days_30E_360(start, end) * coupon_frequency
        elif day_count_convention == "ACT/ACT":
            accrued_days = (d - period_start).days
            total_days = (period_end - period_start).days * int(coupon_frequency)
        elif day_count_convention == "ACT/364":
            accrued_days = (d - period_start).days
            total_days = 364
        elif day_count_convention == "ACT/365":
            accrued_days = (d - period_start).days
            total_days = 365
        else:
            raise ValueError(
                f"Unsupported day count convention: {day_count_convention}"
            )

        if total_days == 0:
            return 0

        fraction = accrued_days / total_days

        # coupon factor (only if rate provided)
        if coupon_rate:
            coupon_factor = coupon_rate * fraction
        else:
            coupon_factor = None

        coupon_schedule.append(
            {
                "coupon_date": d,
                "period_start": period_start,
                "period_end": period_end,
                "coupon_factor": coupon_factor,
            }
        )

        prev = d

    return coupon_schedule


def get_coupon_schedule(isin):
    query = frappe.qb.get_query(
        "Bond Coupon Schedule",
        fields=["coupon_date", "period_start", "period_end", "coupon_factor"],
        filters={"name": isin},
    )
    return query.run(as_dict=True)
