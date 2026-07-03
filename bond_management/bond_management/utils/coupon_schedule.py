from dateutil.relativedelta import relativedelta
import frappe
from frappe.utils import getdate, add_days
from frappe.utils.data import get_last_day


def generate_coupon_schedule(issue_date, maturity_date, coupon_frequency):
    """
    Generate full coupon schedule between issue and maturity.

    Returns:
        List[dict] with:
            coupon_date
            period_start
            period_end
    """

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
        coupon_schedule.append({
            "coupon_date": d,
            "period_start": prev,
            "period_end": add_days(d, -1)  # The period end is the day before the coupon date
        })
        prev = d

    return coupon_schedule