from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

import frappe


MONEY_PRECISION = Decimal("0.0001")
PERCENT_PRECISION = Decimal("0.000000001")
DecimalInput = Decimal | int | float | str | None


def to_decimal(value: DecimalInput, field_label: str = "Value") -> Decimal:
    """Convert framework values and reject malformed or non-finite numbers."""
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        frappe.throw(f"{field_label} must be a valid number")

    if not result.is_finite():
        frappe.throw(f"{field_label} must be a finite number")

    return result


def quantize_money(value) -> Decimal:
    """Apply the app's four-decimal, half-even cash and settlement convention."""
    return to_decimal(value).quantize(MONEY_PRECISION, rounding=ROUND_HALF_EVEN)


def quantize_percent(value) -> Decimal:
    """Persist calculated percentages at nine decimal places using half-even rounding."""
    return to_decimal(value).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_EVEN)
