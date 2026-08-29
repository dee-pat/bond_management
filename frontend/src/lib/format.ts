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

export function formatMoney(value: number, currency: string): string {
  if (!currency) {
    return formatNumber(value, 2);
  }

  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    currencyDisplay: "code",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number, fractionDigits = 2): string {
  return `${formatNumber(value, fractionDigits)}%`;
}
