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

	it("returns a dash for text that is not a calendar date", () => {
		expect(formatDate("not-a-date")).toBe("—");
		expect(formatDate("2026-13-01")).toBe("—");
		expect(formatDate("2026-1-05")).toBe("—");
	});

	it("returns a dash for an impossible day instead of rolling over", () => {
		expect(formatDate("2026-02-30")).toBe("—");
		expect(formatDate("2025-02-29")).toBe("—");
	});

	it("formats the date part of a Frappe datetime", () => {
		expect(formatDate("2026-01-05T10:00:00")).toBe("05 Jan 2026");
		expect(formatDate("2026-01-05 23:59:59.000000")).toBe("05 Jan 2026");
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

	it("drops the sign of zero and of negatives that round to zero", () => {
		expect(formatNumber(-0)).toBe("0");
		expect(formatNumber(-0.4)).toBe("0");
		expect(formatNumber(-0.004, 2)).toBe("0.00");
		expect(formatNumber(-0.005, 2)).toBe("-0.01");
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

	it("returns a dash for non-finite values", () => {
		expect(formatNumber(Number.NaN)).toBe("—");
		expect(formatNumber(Number.POSITIVE_INFINITY)).toBe("—");
		expect(formatNumber(Number.NEGATIVE_INFINITY, 2)).toBe("—");
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

	it("drops the sign of an amount that rounds to zero", () => {
		expect(formatMoney(-0.001, "USD")).toBe(`USD${NBSP}0.00`);
		expect(formatMoney(-0.001, "US")).toBe("US 0.00");
	});

	it("returns a dash for a non-finite amount", () => {
		expect(formatMoney(Number.NaN, "USD")).toBe("—");
		expect(formatMoney(Number.POSITIVE_INFINITY, "")).toBe("—");
	});

	it("normalizes a lower-case currency code", () => {
		expect(formatMoney(1234.5, "usd")).toBe(`USD${NBSP}1,234.50`);
	});

	it("returns the plain number without a currency", () => {
		expect(formatMoney(1234.5, "")).toBe("1,234.50");
	});

	it("falls back to code and number for an invalid currency", () => {
		// Unlike the Intl path, the fallback joins with a normal space (kept on review).
		expect(formatMoney(1234.5, "US")).toBe("US 1,234.50");
	});
});

describe("formatPercent", () => {
	it("appends a percent sign to a two-decimal number", () => {
		expect(formatPercent(12.3456)).toBe("12.35%");
		expect(formatPercent(0)).toBe("0.00%");
		expect(formatPercent(-0.5)).toBe("-0.50%");
	});

	it("returns a dash for a non-finite value", () => {
		expect(formatPercent(Number.NaN)).toBe("—");
	});

	it("does not scale the value", () => {
		expect(formatPercent(0.05, 1)).toBe("0.1%");
	});
});
