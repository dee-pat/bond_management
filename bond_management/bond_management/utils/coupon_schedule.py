import frappe
from dateutil.relativedelta import relativedelta
from frappe.utils import add_days, add_months, getdate
from frappe.utils.data import get_last_day

from bond_management.bond_management.utils.financial import to_decimal


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

    if not issue_date or not maturity_date or coupon_frequency is None:
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

        coupon_factor = to_decimal(coupon_rate) * fraction

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
        parent_doctype="Bond Master",
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
        return to_decimal(0)

    if day_count_convention == "ACT/365":
        return to_decimal((end - start).days) / to_decimal(365)

    if day_count_convention in {"ACT/364", "Actual/364(Kenya)"}:
        return to_decimal((end - start).days) / to_decimal(364)

    if day_count_convention in {"ACT/ACT", "Actual/Actual(ICMA)"}:
        if coupon_frequency <= 0 or 12 % coupon_frequency:
            raise ValueError("Coupon frequency must be a positive divisor of 12")
        if reference_end < end:
            raise ValueError("Reference end date cannot be before end date")

        # ICMA long stubs must be split across their notional coupon periods.
        # Using one denominator for the whole stub is wrong when the periods have
        # different lengths (most visibly around leap years and month ends).
        months_per_period = 12 // coupon_frequency
        preserve_eom = reference_end == get_last_day(reference_end)
        quasi_end = reference_end
        fraction = to_decimal(0)

        while quasi_end > start:
            quasi_start = add_months(quasi_end, -months_per_period)
            if preserve_eom:
                quasi_start = get_last_day(quasi_start)

            overlap_start = max(start, quasi_start)
            overlap_end = min(end, quasi_end)
            if overlap_end > overlap_start:
                denominator = (quasi_end - quasi_start).days * coupon_frequency
                fraction += to_decimal((overlap_end - overlap_start).days) / to_decimal(denominator)

            quasi_end = quasi_start

        return fraction

    if day_count_convention == "30E/360":
        d1 = min(start.day, 30)
        d2 = min(end.day, 30)

        numerator = (end.year - start.year) * 360 + (end.month - start.month) * 30 + (d2 - d1)
        return to_decimal(numerator) / to_decimal(360)

    raise ValueError(f"Unsupported day count convention: {day_count_convention}")
