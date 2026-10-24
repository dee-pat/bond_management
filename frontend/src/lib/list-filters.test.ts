// @vitest-environment happy-dom
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import { settle, withSetup } from "../test-utils/composable";
import { usePagedList } from "./list";
import { useListFilters, usePortfolioFilter } from "./list-filters";

const portfolios = [
	{ name: "PF-1", label: "Growth" },
	{ name: "PF-2", label: "Income" },
];

function mountFilters() {
	const fetchPage = vi.fn(async () => ({
		data: [],
		pagination: { start: 0, page_length: 20, has_more: false },
	}));
	const status = ref("");
	const mounted = withSetup(() => {
		const portfolio = usePortfolioFilter(() => portfolios);
		const list = usePagedList({ fetchPage, sortBy: "statement_date", errorMessage: "Failed." });
		const filters = useListFilters(list, [
			portfolio.filter,
			{ field: "reconciliation_status", label: "Reconciliation Status", selected: status },
		]);
		return { portfolio, list, filters };
	});
	return { ...mounted, status, fetchPage };
}

describe("usePortfolioFilter", () => {
	it("offers every assigned portfolio after the all option", () => {
		const { portfolio } = mountFilters();
		expect(portfolio.hasAssignments.value).toBe(true);
		expect(portfolio.options.value).toEqual([
			{ label: "All assigned portfolios", value: "" },
			{ label: "Growth", value: "PF-1" },
			{ label: "Income", value: "PF-2" },
		]);
	});
});

describe("useListFilters", () => {
	it("routes Select fields to their Select and other fields to the list filter", async () => {
		const { portfolio, list, filters, status, fetchPage } = mountFilters();
		await settle();
		fetchPage.mockClear();

		filters.applyFilter("portfolio_name", "Portfolio Name", "PF-2");
		filters.applyFilter("reconciliation_status", "Reconciliation Status", "Matched");
		filters.applyFilter("isin", "ISIN", "KE001");

		expect(portfolio.selected.value).toBe("PF-2");
		expect(status.value).toBe("Matched");
		expect(list.activeFilter.value).toEqual({ field: "isin", label: "ISIN", value: "KE001" });
		expect(filters.activeFilters.value).toEqual([
			{ field: "portfolio_name", label: "Portfolio Name", value: "Income" },
			{ field: "reconciliation_status", label: "Reconciliation Status", value: "Matched" },
			{ field: "isin", label: "ISIN", value: "KE001" },
		]);
		expect(fetchPage).toHaveBeenCalledTimes(3);
		expect(fetchPage).toHaveBeenLastCalledWith(expect.objectContaining({ start: 0 }));
	});

	it("ignores an empty filter value without reloading", async () => {
		const { filters, fetchPage } = mountFilters();
		await settle();
		fetchPage.mockClear();

		filters.applyFilter("isin", "ISIN", "");

		expect(filters.activeFilters.value).toEqual([]);
		expect(fetchPage).not.toHaveBeenCalled();
	});

	it("clears one filter or all of them, reloading page one each time", async () => {
		const { portfolio, list, filters, status, fetchPage } = mountFilters();
		portfolio.selected.value = "PF-1";
		status.value = "Mismatched";
		list.activeFilter.value = { field: "isin", label: "ISIN", value: "KE001" };
		await settle();
		fetchPage.mockClear();

		filters.clearFilter("reconciliation_status");
		expect(status.value).toBe("");
		expect(filters.activeFilters.value.map((filter) => filter.field)).toEqual([
			"portfolio_name",
			"isin",
		]);

		filters.clearAllFilters();
		expect(portfolio.selected.value).toBe("");
		expect(list.activeFilter.value).toBeNull();
		expect(filters.activeFilters.value).toEqual([]);
		expect(fetchPage).toHaveBeenCalledTimes(2);
	});
});
