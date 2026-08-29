<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import { fetchMarketDates, InvestorApiError, redirectToLogin } from "../lib/api";
import { toFilterValue } from "../lib/list";
import { formatDate } from "../lib/format";
import type { ActiveListFilter, MarketDateListRow, MarketDatePage, SortOrder } from "../types";

const marketDates = ref<MarketDateListRow[]>([]);
const activeFilter = ref<ActiveListFilter | null>(null);
const sortBy = ref("date");
const sortOrder = ref<SortOrder>("desc");
const pagination = ref<MarketDatePage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
let latestRequest = 0;

async function loadMarketDates(
	start = 0,
	append = false,
	pageLength = pagination.value.page_length
): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchMarketDates({
			start,
			pageLength,
			sortBy: sortBy.value || undefined,
			sortOrder: sortBy.value ? sortOrder.value : undefined,
			filterField: activeFilter.value?.field,
			filterValue: activeFilter.value?.value,
		});
		if (requestId !== latestRequest) return;
		marketDates.value = append ? [...marketDates.value, ...response.data] : response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) return;
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Market dates could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) loading.value = false;
	}
}

function applyFilter(field: string, label: string, value: unknown): void {
	const filterValue = toFilterValue(value);
	if (!filterValue) return;
	activeFilter.value = { field, label, value: filterValue };
	void loadMarketDates(0);
}

function clearFilter(): void {
	activeFilter.value = null;
	void loadMarketDates(0);
}

function changeSort(field: string, order: SortOrder): void {
	sortBy.value = field;
	sortOrder.value = order;
	void loadMarketDates(0);
}

function loadMoreMarketDates(): void {
	void loadMarketDates(pagination.value.start + pagination.value.page_length, true);
}

function changePageLength(pageLength: number): void {
	if (pageLength === pagination.value.page_length) return;
	void loadMarketDates(0, false, pageLength);
}

function retryMarketDates(): void {
	void loadMarketDates(0, false);
}

onMounted(() => void loadMarketDates());
</script>

<template>
	<section class="record-surface" aria-label="Bond market date list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<div v-if="loading && marketDates.length === 0" class="surface-state" aria-live="polite">
			Loading market dates…
		</div>

		<div
			v-else-if="error && marketDates.length === 0"
			class="surface-state surface-state--error"
			role="alert"
		>
			<p>{{ error }}</p>
			<button class="secondary-button" type="button" @click="retryMarketDates">Retry</button>
		</div>

		<div
			v-else-if="marketDates.length === 0"
			class="surface-state"
			data-testid="market-dates-empty"
		>
			No market dates match the selected filters.
		</div>

		<template v-else>
			<div v-if="error" class="surface-state surface-state--error" role="alert">
				<p>{{ error }}</p>
				<button class="secondary-button" type="button" @click="retryMarketDates">
					Retry
				</button>
			</div>

			<div class="record-table-wrap">
				<table class="record-table">
					<thead>
						<tr>
							<SortableColumn
								label="Date"
								field="date"
								:sort-by="sortBy"
								:sort-order="sortOrder"
								:disabled="loading"
								@sort="changeSort"
							/>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="marketDate in marketDates"
							:key="marketDate.name"
							data-testid="market-date-row"
						>
							<td data-label="Date">
								<RouterLink
									:to="`/market-dates/${encodeURIComponent(marketDate.name)}`"
									:aria-label="`View market date ${marketDate.name}`"
								>
									{{ formatDate(marketDate.date) }}
								</RouterLink>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<ListPagination
				:has-more="pagination.has_more"
				:item-count="marketDates.length"
				:loading="loading"
				:page-length="pagination.page_length"
				label="Market date list pagination"
				@change-page-length="changePageLength"
				@load-more="loadMoreMarketDates"
			/>
		</template>
	</section>
</template>
