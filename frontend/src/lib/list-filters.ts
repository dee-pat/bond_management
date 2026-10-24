import { computed, ref, type Ref } from "vue";

import { toFilterValue, type PagedList } from "./list";
import type { ActiveListFilter, PortfolioChoice } from "../types";

/** A page-level Select whose value also shows, and clears, as a filter chip. */
export interface SelectFilter {
	field: string;
	label: string;
	selected: Ref<string>;
	/** Chip text for the selected value; defaults to the value itself. */
	display?: (value: string) => string;
}

/** Combine Select filters with the list's click-to-filter column; every change reloads page one. */
export function useListFilters<Row>(list: PagedList<Row>, selectFilters: SelectFilter[]) {
	const activeFilters = computed<ActiveListFilter[]>(() => {
		const filters = selectFilters
			.filter((filter) => filter.selected.value)
			.map(({ field, label, selected, display }) => ({
				field,
				label,
				value: display?.(selected.value) ?? selected.value,
			}));
		return list.activeFilter.value ? [...filters, list.activeFilter.value] : filters;
	});

	function reload(): void {
		void list.load(0);
	}

	function applyFilter(field: string, label: string, value: unknown): void {
		const filterValue = toFilterValue(value);
		if (!filterValue) return;
		const selectFilter = findSelectFilter(field);
		if (selectFilter) selectFilter.selected.value = filterValue;
		else list.activeFilter.value = { field, label, value: filterValue };
		reload();
	}

	function clearFilter(field: string): void {
		const selectFilter = findSelectFilter(field);
		if (selectFilter) selectFilter.selected.value = "";
		if (list.activeFilter.value?.field === field) list.activeFilter.value = null;
		reload();
	}

	function clearAllFilters(): void {
		for (const filter of selectFilters) filter.selected.value = "";
		list.activeFilter.value = null;
		reload();
	}

	function findSelectFilter(field: string): SelectFilter | undefined {
		return selectFilters.find((filter) => filter.field === field);
	}

	return { activeFilters, reload, applyFilter, clearFilter, clearAllFilters };
}

/** The Portfolio Name Select over the user's assigned portfolios. */
export function usePortfolioFilter(portfolios: () => PortfolioChoice[]) {
	const selected = ref("");
	const hasAssignments = computed(() => portfolios().length > 0);
	const options = computed(() => [
		{ label: "All assigned portfolios", value: "" },
		...portfolios().map((portfolio) => ({ label: portfolio.label, value: portfolio.name })),
	]);
	const filter: SelectFilter = {
		field: "portfolio_name",
		label: "Portfolio Name",
		selected,
		display: (name) => portfolios().find((portfolio) => portfolio.name === name)?.label ?? name,
	};
	return { selected, hasAssignments, options, filter };
}
