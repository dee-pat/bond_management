<script setup lang="ts">
import { RouterLink } from "vue-router";
import { Button } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import SurfaceState from "../components/SurfaceState.vue";
import { useInvestorApi } from "../lib/api";
import { usePagedList } from "../lib/list";
import { formatDate, formatNumber } from "../lib/format";
import type { ExchangeRateListRow } from "../types";

const api = useInvestorApi();
const {
	rows: exchangeRates,
	activeFilter,
	sortBy,
	sortOrder,
	pagination,
	loading,
	error,
	applyFilter,
	clearFilter,
	changeSort,
	loadMore: loadMoreExchangeRates,
	changePageLength,
	retry: retryExchangeRates,
} = usePagedList<ExchangeRateListRow>({
	fetchPage: api.fetchExchangeRates,
	sortBy: "rate_date",
	errorMessage: "Exchange rates could not be loaded. Please retry.",
});
</script>

<template>
	<section class="record-surface" aria-label="Bond exchange rate list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<SurfaceState
			v-if="loading && exchangeRates.length === 0"
			:loading="loading"
			loading-text="Loading exchange rates…"
		/>

		<SurfaceState
			v-else-if="error && exchangeRates.length === 0"
			:error="error"
			@retry="retryExchangeRates"
		/>

		<div
			v-else-if="exchangeRates.length === 0"
			class="surface-state"
			data-testid="exchange-rates-empty"
		>
			No exchange rates match the selected filters.
		</div>

		<template v-else>
			<SurfaceState v-if="error" :error="error" @retry="retryExchangeRates" />

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
