<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { Button } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import { toFilterValue } from "../lib/list";
import { formatDate, formatNumber } from "../lib/format";
import type { ActiveListFilter, ExchangeRateListRow, ExchangeRatePage, SortOrder } from "../types";

const exchangeRates = ref<ExchangeRateListRow[]>([]);
const activeFilter = ref<ActiveListFilter | null>(null);
const sortBy = ref("rate_date");
const sortOrder = ref<SortOrder>("desc");
const pagination = ref<ExchangeRatePage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
const api = useInvestorApi();
let latestRequest = 0;

async function loadExchangeRates(
	start = 0,
	append = false,
	pageLength = pagination.value.page_length
): Promise<void> {
	if (append && (loading.value || !pagination.value.has_more)) return;

	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;
	if (!append) {
		exchangeRates.value = [];
		pagination.value = { start: 0, page_length: pageLength, has_more: false };
	}

	try {
		const response = await api.fetchExchangeRates({
			start,
			pageLength,
			sortBy: sortBy.value || undefined,
			sortOrder: sortBy.value ? sortOrder.value : undefined,
			filterField: activeFilter.value?.field,
			filterValue: activeFilter.value?.value,
		});
		if (requestId !== latestRequest) return;
		exchangeRates.value = append ? [...exchangeRates.value, ...response.data] : response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) return;
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Exchange rates could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) loading.value = false;
	}
}

function applyFilter(field: string, label: string, value: unknown): void {
	const filterValue = toFilterValue(value);
	if (!filterValue) return;
	activeFilter.value = { field, label, value: filterValue };
	void loadExchangeRates(0);
}

function clearFilter(): void {
	activeFilter.value = null;
	void loadExchangeRates(0);
}

function changeSort(field: string, order: SortOrder): void {
	sortBy.value = field;
	sortOrder.value = order;
	void loadExchangeRates(0);
}

function loadMoreExchangeRates(): void {
	void loadExchangeRates(pagination.value.start + pagination.value.page_length, true);
}

function changePageLength(pageLength: number): void {
	if (pageLength === pagination.value.page_length) return;
	void loadExchangeRates(0, false, pageLength);
}

function retryExchangeRates(): void {
	void loadExchangeRates(0, false);
}

onMounted(() => void loadExchangeRates());
</script>

<template>
	<section class="record-surface" aria-label="Bond exchange rate list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<div v-if="loading && exchangeRates.length === 0" class="surface-state" aria-live="polite">
			Loading exchange rates…
		</div>

		<div
			v-else-if="error && exchangeRates.length === 0"
			class="surface-state surface-state--error"
			role="alert"
		>
			<p>{{ error }}</p>
			<Button label="Retry" variant="outline" @click="retryExchangeRates" />
		</div>

		<div
			v-else-if="exchangeRates.length === 0"
			class="surface-state"
			data-testid="exchange-rates-empty"
		>
			No exchange rates match the selected filters.
		</div>

		<template v-else>
			<div v-if="error" class="surface-state surface-state--error" role="alert">
				<p>{{ error }}</p>
				<Button label="Retry" variant="outline" @click="retryExchangeRates" />
			</div>

			<DataList
				:items="exchangeRates"
				:columns="[
					'minmax(9rem,1fr)',
					'minmax(10rem,1fr)',
					'minmax(9rem,1fr)',
					'minmax(10rem,1fr)',
					'minmax(10rem,1fr)',
				]"
				row-key="name"
				row-test-id="exchange-rate-row"
			>
				<template #header>
					<SortableColumn
						label="Rate Date"
						field="rate_date"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="From Currency"
						field="from_currency"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="To Currency"
						field="to_currency"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Rate"
						field="rate"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Reverse Rate"
						field="reverse_rate"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
				</template>
				<template #row="{ item: exchangeRate }">
					<ListCell data-label="Rate Date">
						<span>{{ formatDate(exchangeRate.rate_date) }}</span>
					</ListCell>
					<ListCell data-label="From Currency">
						<RouterLink
							:to="`/exchange-rates/${encodeURIComponent(exchangeRate.name)}`"
							:aria-label="`View exchange rate ${exchangeRate.name}`"
						>
							{{ exchangeRate.from_currency }}
						</RouterLink>
						<Button
							class="list-filter-action"
							variant="ghost"
							size="sm"
							:label="`Filter From Currency by ${exchangeRate.from_currency}`"
							@click="
								applyFilter(
									'from_currency',
									'From Currency',
									exchangeRate.from_currency
								)
							"
						>
							Filter
						</Button>
					</ListCell>
					<ListCell data-label="To Currency">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter To Currency by ${exchangeRate.to_currency}`"
							@click="
								applyFilter('to_currency', 'To Currency', exchangeRate.to_currency)
							"
						>
							{{ exchangeRate.to_currency }}
						</Button>
					</ListCell>
					<ListCell data-label="Rate">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Rate by ${exchangeRate.rate}`"
							@click="applyFilter('rate', 'Rate', exchangeRate.rate)"
						>
							{{ formatNumber(exchangeRate.rate, 12) }}
						</Button>
					</ListCell>
					<ListCell data-label="Reverse Rate">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Reverse Rate by ${exchangeRate.reverse_rate}`"
							@click="
								applyFilter(
									'reverse_rate',
									'Reverse Rate',
									exchangeRate.reverse_rate
								)
							"
						>
							{{ formatNumber(exchangeRate.reverse_rate, 12) }}
						</Button>
					</ListCell>
				</template>
			</DataList>

			<ListPagination
				:has-more="pagination.has_more"
				:item-count="exchangeRates.length"
				:loading="loading"
				:page-length="pagination.page_length"
				label="Exchange rate list pagination"
				@change-page-length="changePageLength"
				@load-more="loadMoreExchangeRates"
			/>
		</template>
	</section>
</template>
