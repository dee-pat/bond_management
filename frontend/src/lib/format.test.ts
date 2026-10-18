import { describe, expect, it } from "vitest";

import { formatDate, formatMoney, formatNumber, formatPercent } from "./format";

// Intl separates a currency code from its amount with a no-break space.
const NBSP = " ";

describe("formatDate", () => {
	it("formats an ISO date as a UTC calendar date", () => {
		expect(formatDate("2026-01-05")).toBe("05 Jan 2026");
		expect(formatDate("2024-02-29")).toBe("29 Feb 2024");
	});

	it("returns a dash for empty input", () => {
		expect(formatDate("")).toBe("—");
	});

	it("throws for text that is not a date", () => {
		// TODO(review): an unparseable value throws a RangeError and breaks the
		// render instead of falling back to the dash or the raw value.
		expect(() => formatDate("not-a-date")).toThrow(RangeError);
		expect(() => formatDate("2026-13-01")).toThrow(RangeError);
	});

	it("throws for a datetime string", () => {
		// TODO(review): a timestamp value becomes "...T10:00:00T00:00:00Z" and throws.
		expect(() => formatDate("2026-01-05T10:00:00")).toThrow(RangeError);
	});

	it("rolls an impossible day into the next month", () => {
		// TODO(review): 30 February silently renders as 2 March.
		expect(formatDate("2026-02-30")).toBe("02 Mar 2026");
	});
});

describe("formatNumber", () => {
	it("groups thousands with no decimals by default", () => {
		expect(formatNumber(1234567)).toBe("1,234,567");
	});

	it("formats zero and negative values", () => {
		expect(formatNumber(0)).toBe("0");
		expect(formatNumber(-1234.5, 2)).toBe("-1,234.50");
	});

	it("keeps the sign of negative zero", () => {
		// TODO(review): -0, and negatives that round to zero, render as "-0".
		expect(formatNumber(-0)).toBe("-0");
		expect(formatNumber(-0.4)).toBe("-0");
	});

	it("formats very large values in full", () => {
		expect(formatNumber(123456789012.345, 2)).toBe("123,456,789,012.35");
		expect(formatNumber(1e21)).toBe("1,000,000,000,000,000,000,000");
	});

	it("rounds half away from zero at the fractionDigits boundary", () => {
		expect(formatNumber(1.234, 2)).toBe("1.23");
		expect(formatNumber(1.235, 2)).toBe("1.24");
		expect(formatNumber(1.236, 2)).toBe("1.24");
		expect(formatNumber(1.4)).toBe("1");
		expect(formatNumber(1.5)).toBe("2");
		expect(formatNumber(2.5)).toBe("3");
		expect(formatNumber(-1.5)).toBe("-2");
	});

	it("pads to the requested fraction digits", () => {
		expect(formatNumber(2, 3)).toBe("2.000");
	});

	it("renders non-finite values as Intl does", () => {
		// TODO(review): NaN and Infinity reach the page as "NaN" and "∞".
		expect(formatNumber(Number.NaN)).toBe("NaN");
		expect(formatNumber(Number.POSITIVE_INFINITY)).toBe("∞");
	});
});

describe("formatMoney", () => {
	it("prefixes the ISO currency code for each currency", () => {
		expect(formatMoney(1234.5, "USD")).toBe(`USD${NBSP}1,234.50`);
		expect(formatMoney(1234.5, "EUR")).toBe(`EUR${NBSP}1,234.50`);
		expect(formatMoney(1234.5, "GBP")).toBe(`GBP${NBSP}1,234.50`);
		expect(formatMoney(1234.5, "KES")).toBe(`KES${NBSP}1,234.50`);
	});

	it("uses the requested fraction digits regardless of currency", () => {
		expect(formatMoney(1234.5, "JPY")).toBe(`JPY${NBSP}1,234.50`);
		expect(formatMoney(1234.5675, "USD", 3)).toBe(`USD${NBSP}1,234.568`);
	});

	it("formats zero and negative amounts", () => {
		expect(formatMoney(0, "USD")).toBe(`USD${NBSP}0.00`);
		expect(formatMoney(-1234.5, "USD")).toBe(`-USD${NBSP}1,234.50`);
	});

	it("normalizes a lower-case currency code", () => {
		expect(formatMoney(1234.5, "usd")).toBe(`USD${NBSP}1,234.50`);
	});

	it("returns the plain number without a currency", () => {
		expect(formatMoney(1234.5, "")).toBe("1,234.50");
	});

	it("falls back to code and number for an invalid currency", () => {
		// TODO(review): the fallback joins with a normal space, the Intl path with a
		// no-break space, so the amount can wrap away from its code.
		expect(formatMoney(1234.5, "US")).toBe("US 1,234.50");
	});
});

describe("formatPercent", () => {
	it("appends a percent sign to a two-decimal number", () => {
		expect(formatPercent(12.3456)).toBe("12.35%");
		expect(formatPercent(0)).toBe("0.00%");
		expect(formatPercent(-0.5)).toBe("-0.50%");
	});

	it("does not scale the value", () => {
		expect(formatPercent(0.05, 1)).toBe("0.1%");
	});
});
