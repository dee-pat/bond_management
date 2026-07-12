from dateutil.relativedelta import relativedelta

import frappe
from frappe.utils import add_days, add_months, getdate
from frappe.utils.data import get_last_day


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
    except (TypeError, ValueError):
        frappe.throw("Coupon Frequency must be a number")

    if coupon_frequency <= 0 or 12 % coupon_frequency:
        frappe.throw("Coupon Frequency must be a positive divisor of 12")

    step = relativedelta(months=int(12 / coupon_frequency))

    # Step 1: generate schedule backwards
    dates = []
    current = maturity_date
    eom = maturity_date == get_last_day(maturity_date)

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

        fraction = year_fraction(
            day_count_convention=day_count_convention,
            start_date=period_start,
            end_date=d,
            coupon_frequency=coupon_frequency,
        )

        coupon_factor = (coupon_rate or 0) * fraction

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
        filters={
            "parent": isin,
            "parenttype": "Bond Master",
            "parentfield": "coupon_schedule",
        },
        order_by="coupon_date asc",
        ignore_permissions=False,
    )
    return query.run(as_dict=True)


def year_fraction(
    day_count_convention,
    start_date,
    end_date,
    coupon_frequency,
    reference_end_date=None,
):
    start = getdate(start_date)
    end = getdate(end_date)
    reference_end = getdate(reference_end_date) if reference_end_date else end
    coupon_frequency = int(coupon_frequency)

    if end <= start:
        return 0

    if day_count_convention == "ACT/365":
        return (end - start).days / 365

    if day_count_convention in {"ACT/364", "Actual/364(Kenya)"}:
        return (end - start).days / 364

    if day_count_convention in {"ACT/ACT", "Actual/Actual(ICMA)"}:
        quasi_start = add_months(reference_end, -(12 // coupon_frequency))
        if reference_end == get_last_day(reference_end):
            quasi_start = get_last_day(quasi_start)
        denominator = (reference_end - quasi_start).days * coupon_frequency
        return (end - start).days / denominator

    if day_count_convention == "30E/360":
        d1 = min(start.day, 30)
        d2 = min(end.day, 30)

        return (
            (end.year - start.year) * 360 + (end.month - start.month) * 30 + (d2 - d1)
        ) / 360

    raise ValueError(f"Unsupported day count convention: {day_count_convention}")
