from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.utils import add_days, add_months, getdate
from frappe.utils.data import get_last_day

from bond_management.bond_management.utils.financial import to_decimal

KENYA_DAY_COUNT_CONVENTIONS = {"ACT/364(Kenya)", "ACT/364(KENYA)", "Actual/364(Kenya)"}
_KENYA_DAY_COUNT_KEYS = frozenset(convention.casefold() for convention in KENYA_DAY_COUNT_CONVENTIONS)
KENYA_COUPON_PERIOD_DAYS = 182

DateInput = date | str | None


def is_kenya_day_count_convention(day_count_convention: str | None) -> bool:
    """Return whether the convention is Actual/364(Kenya), matched case-insensitively."""
    normalized = str(day_count_convention or "").casefold()
    return normalized in _KENYA_DAY_COUNT_KEYS


def generate_coupon_schedule(
    issue_date: DateInput,
    maturity_date: DateInput,
    coupon_frequency: int | str | None,
    coupon_rate: Decimal | float | int | str | None,
    first_coupon_date: DateInput,
    day_count_convention: str | None,
    principal_dates: Iterable[DateInput] | None = None,
) -> list[dict]:
    """Return Bond Master coupon schedule rows from issue date to maturity.

    Coupon dates step back from maturity: 182 days for Actual/364(Kenya), which
    needs frequency 2, ignores ``first_coupon_date`` and requires every
    principal date on the cadence; otherwise ``12 / coupon_frequency`` months,
    kept at month end when maturity is one, with ``first_coupon_date`` starting
    a stub period. ``coupon_factor`` is ``coupon_rate * year_fraction`` under
    ``day_count_convention`` (30E/360, Actual/Actual(ICMA) or Actual/364(Kenya)).

    Each row holds ``coupon_date``, ``period_start`` (the previous coupon date,
    or the issue date), ``period_end`` (the day before ``coupon_date``) and the
    unquantized ``Decimal`` ``coupon_factor``, a percentage of face value. An
    empty list means issue date, maturity date or frequency is missing.
    """
    issue_date = getdate(issue_date)
    maturity_date = getdate(maturity_date)
    first_coupon_date = getdate(first_coupon_date) if first_coupon_date else None

    if not issue_date or not maturity_date or coupon_frequency is None:
        return []

    if issue_date >= maturity_date:
        frappe.throw(_("Issue date must be before maturity date"))

    coupon_frequency = _validated_coupon_frequency(coupon_frequency)
    kenya_convention = is_kenya_day_count_convention(day_count_convention)
    if first_coupon_date and not kenya_convention:
        _validate_first_coupon_date(first_coupon_date, issue_date, maturity_date)

    principal_dates = [getdate(repayment_date) for repayment_date in principal_dates or [] if repayment_date]
    if kenya_convention and coupon_frequency != 2:
        frappe.throw(_("Actual/364(Kenya) requires a semi-annual coupon frequency of 2"))

    dates = _coupon_dates_backwards(issue_date, maturity_date, coupon_frequency, kenya_convention)
    if kenya_convention:
        _validate_kenya_principal_dates(dates, principal_dates)
    elif first_coupon_date:
        dates = _apply_first_coupon_stub(dates, first_coupon_date)

    return _build_schedule_rows(dates, issue_date, coupon_rate, day_count_convention, coupon_frequency)


def year_fraction(
    day_count_convention: str | None,
    start_date: DateInput,
    end_date: DateInput,
    coupon_frequency: int | str,
    reference_end_date: DateInput = None,
) -> Decimal:
    """Return the year fraction from ``start_date`` to ``end_date``; 0 when end is not after start.

    An unsupported convention is user input: Bond Master's controller runs
    before Frappe validates Select options, so it raises a validation error.
    The ``ValueError`` raises are internal invariants that validated callers
    cannot reach: the coupon schedule validates frequency first, stored bonds
    hold a validated frequency, and accrual callers pass a reference end on or
    after the end date.
    """
    start = getdate(start_date)
    end = getdate(end_date)
    reference_end = getdate(reference_end_date) if reference_end_date else end
    coupon_frequency = int(coupon_frequency)

    if end <= start:
        return to_decimal(0)

    if day_count_convention == "ACT/365":
        return to_decimal((end - start).days) / to_decimal(365)

    if day_count_convention == "ACT/364" or is_kenya_day_count_convention(day_count_convention):
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

    frappe.throw(_("Unsupported day count convention: {0}").format(day_count_convention))


def _validated_coupon_frequency(coupon_frequency: int | str) -> int:
    try:
        coupon_frequency = int(coupon_frequency)
    except (TypeError, ValueError):
        frappe.throw(_("Coupon Frequency must be a number"))

    if coupon_frequency <= 0 or 12 % coupon_frequency:
        frappe.throw(_("Coupon Frequency must be a positive divisor of 12"))
    return coupon_frequency


def _validate_first_coupon_date(first_coupon_date: date, issue_date: date, maturity_date: date) -> None:
    if first_coupon_date <= issue_date:
        frappe.throw(_("First Coupon Date must be after Issue Date"))

    if first_coupon_date >= maturity_date:
        frappe.throw(_("First Coupon Date must be before Maturity Date"))


def _coupon_dates_backwards(
    issue_date: date,
    maturity_date: date,
    coupon_frequency: int,
    kenya_convention: bool,
) -> list[date]:
    """Return ascending coupon dates stepped back from maturity, all after the issue date."""
    dates = []
    current = maturity_date
    if kenya_convention:
        while current > issue_date:
            dates.append(current)
            current -= timedelta(days=KENYA_COUPON_PERIOD_DAYS)
    else:
        step = relativedelta(months=int(12 / coupon_frequency))
        eom = maturity_date == get_last_day(maturity_date)

        while current > issue_date:
            dates.append(current)
            current = current - step

            if eom:
                current = get_last_day(current)

    return sorted(dates)


def _apply_first_coupon_stub(dates: list[date], first_coupon_date: date) -> list[date]:
    """Replace generated dates up to the first coupon date with that date."""
    return [first_coupon_date, *(d for d in dates if d > first_coupon_date)]


def _validate_kenya_principal_dates(coupon_dates: list[date], principal_dates: list[date]) -> None:
    # The latest contractual repayment date anchors the Kenya cadence. Earlier
    # repayments must already fall on one of those dates; they must not mutate
    # the cadence by introducing additional coupon boundaries.
    invalid_principal_dates = sorted(set(principal_dates) - set(coupon_dates))
    if invalid_principal_dates:
        frappe.throw(
            _("Repayment Date {0} must match the 182-day coupon schedule").format(invalid_principal_dates[0])
        )


def _build_schedule_rows(
    dates: list[date],
    issue_date: date,
    coupon_rate: Decimal | float | int | str | None,
    day_count_convention: str | None,
    coupon_frequency: int,
) -> list[dict]:
    coupon_schedule = []
    prev = issue_date

    for d in dates:
        period_start = prev
        period_end = add_days(d, -1)

        coupon_factor = to_decimal(coupon_rate) * year_fraction(
            day_count_convention=day_count_convention,
            start_date=period_start,
            end_date=d,
            coupon_frequency=coupon_frequency,
        )

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
