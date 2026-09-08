export function formatDate(value: string): string {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export function formatNumber(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

export function formatMoney(value: number, currency: string, fractionDigits = 2): string {
  const formattedValue = formatNumber(value, fractionDigits);
  if (!currency) {
    return formattedValue;
  }

  try {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency,
      currencyDisplay: "code",
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(value);
  } catch {
    return `${currency} ${formattedValue}`;
  }
}

export function formatPercent(value: number, fractionDigits = 2): string {
  return `${formatNumber(value, fractionDigits)}%`;
}
