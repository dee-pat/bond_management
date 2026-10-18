const EMPTY_VALUE = "—";

// A calendar date, optionally followed by a Frappe time part ("T" or space).
const ISO_DATE = /^(\d{4}-\d{2}-\d{2})(?:$|[T ])/;

export function formatDate(value: string): string {
  const isoDate = ISO_DATE.exec(value ?? "")?.[1];
  if (!isoDate) {
    return EMPTY_VALUE;
  }

  const date = new Date(`${isoDate}T00:00:00Z`);
  // Date rolls 2026-02-30 over to 2 March; reject any date that does not round-trip.
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== isoDate) {
    return EMPTY_VALUE;
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatNumber(value: number, fractionDigits = 0): string {
  if (!Number.isFinite(value)) {
    return EMPTY_VALUE;
  }

  return withoutNegativeZero(
    new Intl.NumberFormat("en-GB", {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(value)
  );
}

export function formatMoney(value: number, currency: string, fractionDigits = 2): string {
  const formattedValue = formatNumber(value, fractionDigits);
  if (!currency || !Number.isFinite(value)) {
    return formattedValue;
  }

  try {
    return withoutNegativeZero(
      new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency,
        currencyDisplay: "code",
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
      }).format(value)
    );
  } catch {
    return `${currency} ${formattedValue}`;
  }
}

export function formatPercent(value: number, fractionDigits = 2): string {
  if (!Number.isFinite(value)) {
    return EMPTY_VALUE;
  }

  return `${formatNumber(value, fractionDigits)}%`;
}

// Intl keeps the sign of -0 and of negatives that round to zero ("-0.00").
// signDisplay: "negative" drops it, but older Safari throws on that option.
function withoutNegativeZero(formatted: string): string {
  return formatted.startsWith("-") && !/[1-9]/.test(formatted) ? formatted.slice(1) : formatted;
}
