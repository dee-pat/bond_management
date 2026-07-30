from decimal import ROUND_HALF_EVEN, Decimal


MONEY_PRECISION = Decimal("0.0001")
PERCENT_PRECISION = Decimal("0.000000001")
DecimalInput = Decimal | int | float | str | None


def to_decimal(value: DecimalInput) -> Decimal:
    """Convert framework values without introducing binary floating-point noise."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def quantize_money(value) -> Decimal:
    """Apply the app's four-decimal, half-even cash and settlement convention."""
    return to_decimal(value).quantize(MONEY_PRECISION, rounding=ROUND_HALF_EVEN)


def quantize_percent(value) -> Decimal:
    """Persist calculated percentages at nine decimal places using half-even rounding."""
    return to_decimal(value).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_EVEN)
