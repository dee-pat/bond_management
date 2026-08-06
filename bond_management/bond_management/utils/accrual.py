from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe.utils import getdate

from bond_management.bond_management.utils.coupon_schedule import (
    is_kenya_day_count_convention,
    year_fraction,
)
from bond_management.bond_management.utils.financial import (
    PERCENT_PRECISION,
    quantize_percent,
    to_decimal,
)

DAYS_PER_YEAR = Decimal(365)


def get_coupon_period(coupon_schedule, settlement_date):
    settlement_date = getdate(settlement_date)

    if not coupon_schedule or not settlement_date:
        return None
    period = None
    for row in coupon_schedule:
        start = getdate(row.get("period_start"))
        end = getdate(row.get("period_end"))
        if start and end:
            if start <= settlement_date <= end:
                period = row
                break

    return period


def calculate_accrued_fraction(
    coupon_schedule,
    settlement_date,
    day_count_convention,
    face_value_per_unit,
    coupon_frequency,
    coupon_rate,
):
    period = get_coupon_period(coupon_schedule, settlement_date)

    if not period:
        return to_decimal(0)

    start = getdate(period.get("period_start"))
    settlement = getdate(settlement_date)
    if is_kenya_day_count_convention(day_count_convention):
        coupon_date = getdate(period.get("coupon_date")) if period.get("coupon_date") else None
        period_days = (coupon_date - start).days if coupon_date else 0
        elapsed_days = (settlement - start).days
        if period_days <= 0:
            return to_decimal(0)

        period_fraction = to_decimal(elapsed_days) / to_decimal(period_days)
        coupon_factor = to_decimal(
            period.get("coupon_factor")
            if period.get("coupon_factor") is not None
            else to_decimal(coupon_rate) / to_decimal(coupon_frequency)
        )
        return coupon_factor / to_decimal(100) * to_decimal(face_value_per_unit) * period_fraction

    fraction = year_fraction(
        day_count_convention=day_count_convention,
        start_date=start,
        end_date=settlement,
        coupon_frequency=coupon_frequency,
        reference_end_date=period.get("coupon_date"),
    )
    return to_decimal(coupon_rate) / to_decimal(100) * to_decimal(face_value_per_unit) * fraction


def calculate_principal_factor(isin, date):
    bond_doc = frappe.get_doc("Bond Master", isin)
    return calculate_principal_factor_from_schedule(bond_doc.get("principal_schedule"), date)


def calculate_coupon_principal_factor(isin, coupon_date):
    """Return principal outstanding immediately before a same-day repayment."""
    bond_doc = frappe.get_doc("Bond Master", isin)
    return calculate_principal_factor_from_schedule(
        bond_doc.get("principal_schedule"), coupon_date, include_repayment_on_date=False
    )


def calculate_principal_factor_from_schedule(
    principal_schedule, date, *, include_repayment_on_date: bool = True
):
    """Return outstanding principal after payments through ``date`` by default.

    Coupon entitlement is the distinct exception: pass
    ``include_repayment_on_date=False`` to use principal immediately before a
    repayment made on the coupon date.
    """

    settlement_date = getdate(date)
    principal_factor = to_decimal(1)

    for period in principal_schedule:
        repayment_date = getdate(period.get("repayment_date"))
        repayment_is_effective = repayment_date and (
            repayment_date <= settlement_date
            if include_repayment_on_date
            else repayment_date < settlement_date
        )
        if repayment_is_effective:
            principal_factor -= to_decimal(period.get("repayment_percent")) / to_decimal(100)

    principal_factor = quantize_percent(principal_factor)
    return to_decimal(0) if abs(principal_factor) <= PERCENT_PRECISION else principal_factor


def calculate_weighted_average_repayment(principal_schedule, valuation_date):
    """Return the remaining-principal weighted repayment date and exact years.

    Repayments on or before the valuation date are no longer future principal
    cash flows and are excluded. The displayed date is rounded to the nearest
    whole day using half-up rounding, while the returned year value preserves
    the unrounded weighted day count for yield-curve positioning.
    """
    if not valuation_date:
        return None, None

    valuation_date = getdate(valuation_date)
    remaining_repayments = []

    for period in principal_schedule or []:
        raw_repayment_date = period.get("repayment_date")
        if not raw_repayment_date:
            continue

        repayment_date = getdate(raw_repayment_date)
        principal_units = Decimal(str(period.get("principal_units") or 0))
        if repayment_date <= valuation_date or principal_units <= 0:
            continue

        remaining_repayments.append((repayment_date, principal_units))

    total_principal = sum((principal for _, principal in remaining_repayments), Decimal(0))
    if not total_principal:
        return None, None

    weighted_days = (
        sum(
            (Decimal((repayment_date - valuation_date).days) * principal)
            for repayment_date, principal in remaining_repayments
        )
        / total_principal
    )
    rounded_days = int(weighted_days.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    return valuation_date + timedelta(days=rounded_days), weighted_days / DAYS_PER_YEAR


def unit_accrued_interest_from_bond(bond_doc, settlement_date):
    settlement_date = getdate(settlement_date)
    principal_factor = calculate_principal_factor_from_schedule(
        bond_doc.get("principal_schedule"), settlement_date
    )
    schedule = [
        row.as_dict() if callable(getattr(row, "as_dict", None)) else row
        for row in bond_doc.get("coupon_schedule")
    ]
    fraction = calculate_accrued_fraction(
        schedule,
        settlement_date,
        bond_doc.get("day_count_convention"),
        bond_doc.get("face_value_per_unit"),
        bond_doc.get("coupon_frequency"),
        bond_doc.get("coupon_rate"),
    )
    return fraction * principal_factor


def unit_accrued_interest(isin=None, settlement_date=None):
    if not isin or not settlement_date:
        return to_decimal(0)

    settlement_date = getdate(settlement_date)

    bond_doc = frappe.get_doc("Bond Master", isin)

    return unit_accrued_interest_from_bond(bond_doc, settlement_date)


def get_accrued_interest(isin=None, settlement_date=None, quantity_face_value=None):
    if not isin or not settlement_date or not quantity_face_value:
        return to_decimal(0)
    settlement_date = getdate(settlement_date)

    return unit_accrued_interest(isin=isin, settlement_date=settlement_date) * to_decimal(quantity_face_value)
