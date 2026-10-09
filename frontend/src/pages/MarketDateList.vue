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
import { formatDate } from "../lib/format";
import type { MarketDateListRow } from "../types";

const api = useInvestorApi();
const {
	rows: marketDates,
	activeFilter,
	sortBy,
	sortOrder,
	pagination,
	loading,
	error,
	applyFilter,
	clearFilter,
	changeSort,
	loadMore: loadMoreMarketDates,
	changePageLength,
	retry: retryMarketDates,
} = usePagedList<MarketDateListRow>({
	fetchPage: api.fetchMarketDates,
	sortBy: "date",
	errorMessage: "Market dates could not be loaded. Please retry.",
});
</script>

<template>
	<section class="record-surface" aria-label="Bond market date list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<SurfaceState
			v-if="loading && marketDates.length === 0"
			:loading="loading"
			loading-text="Loading market dates…"
		/>

		<SurfaceState
			v-else-if="error && marketDates.length === 0"
			:error="error"
			@retry="retryMarketDates"
		/>

		<div
			v-else-if="marketDates.length === 0"
			class="surface-state"
			data-testid="market-dates-empty"
		>
			No market dates match the selected filters.
		</div>

		<template v-else>
			<SurfaceState v-if="error" :error="error" @retry="retryMarketDates" />

			<DataList
				:items="marketDates"
				:columns="['minmax(12rem,1fr)']"
				row-key="name"
				row-test-id="market-date-row"
			>
				<template #header>
					<SortableColumn
						label="Date"
						field="date"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
				</template>
				<template #row="{ item: marketDate }">
					<ListCell data-label="Date">
						<RouterLink
							:to="`/market-dates/${encodeURIComponent(marketDate.name)}`"
							:aria-label="`View market date ${marketDate.name}`"
						>
							{{ formatDate(marketDate.date) }}
						</RouterLink>
					</ListCell>
				</template>
			</DataList>

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
