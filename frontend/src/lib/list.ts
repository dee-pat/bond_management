import { onMounted, ref, shallowRef } from "vue";

import { InvestorApiError, redirectToLogin } from "./api";
import type { ActiveListFilter, SortOrder } from "../types";

interface ListPagination {
	start: number;
	page_length: number;
	has_more: boolean;
}

interface PagedListResponse<Row> {
	data: Row[];
	pagination: ListPagination;
}

interface PagedListParameters {
	start: number;
	pageLength: number;
	sortBy?: string;
	sortOrder?: SortOrder;
	filterField?: string;
	filterValue?: string;
}

interface PagedListOptions<Row> {
	fetchPage: (parameters: PagedListParameters) => Promise<PagedListResponse<Row>>;
	sortBy: string;
	errorMessage: string;
}

export function usePagedList<Row>(options: PagedListOptions<Row>) {
	const rows = shallowRef<Row[]>([]);
	const activeFilter = ref<ActiveListFilter | null>(null);
	const sortBy = ref(options.sortBy);
	const sortOrder = ref<SortOrder>("desc");
	const pagination = ref<ListPagination>({ start: 0, page_length: 20, has_more: false });
	const loading = ref(true);
	const error = ref<string | null>(null);
	let latestRequest = 0;

	async function load(
		start = 0,
		append = false,
		pageLength = pagination.value.page_length
	): Promise<void> {
		if (append && (loading.value || !pagination.value.has_more)) return;

		const requestId = ++latestRequest;
		loading.value = true;
		error.value = null;
		if (!append) {
			rows.value = [];
			pagination.value = { start: 0, page_length: pageLength, has_more: false };
		}

		try {
			const response = await options.fetchPage({
				start,
				pageLength,
				sortBy: sortBy.value || undefined,
				sortOrder: sortBy.value ? sortOrder.value : undefined,
				filterField: activeFilter.value?.field,
				filterValue: activeFilter.value?.value,
			});
			if (requestId !== latestRequest) return;
			rows.value = append ? [...rows.value, ...response.data] : response.data;
			pagination.value = response.pagination;
		} catch (caughtError) {
			if (requestId !== latestRequest) return;
			if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
				redirectToLogin();
				return;
			}
			error.value = options.errorMessage;
		} finally {
			if (requestId === latestRequest) loading.value = false;
		}
	}

	function applyFilter(field: string, label: string, value: unknown): void {
		const filterValue = toFilterValue(value);
		if (!filterValue) return;
		activeFilter.value = { field, label, value: filterValue };
		void load(0);
	}

	function clearFilter(): void {
		activeFilter.value = null;
		void load(0);
	}

	function changeSort(field: string, order: SortOrder): void {
		sortBy.value = field;
		sortOrder.value = order;
		void load(0);
	}

	function loadMore(): void {
		void load(pagination.value.start + pagination.value.page_length, true);
	}

	function changePageLength(pageLength: number): void {
		if (pageLength === pagination.value.page_length) return;
		void load(0, false, pageLength);
	}

	function retry(): void {
		void load(0, false);
	}

	onMounted(() => void load());

	return {
		rows,
		activeFilter,
		sortBy,
		sortOrder,
		pagination,
		loading,
		error,
		load,
		applyFilter,
		clearFilter,
		changeSort,
		loadMore,
		changePageLength,
		retry,
	};
}

export function toFilterValue(value: unknown): string | null {
	if (value === null || value === undefined || value === "") return null;
	return String(value);
}
