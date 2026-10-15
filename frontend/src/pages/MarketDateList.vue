<script setup lang="ts">
import { RouterLink } from "vue-router";
import { ListCell } from "frappe-ui/list";

import ListFilterBar from "../components/ListFilterBar.vue";
import PagedRecordList from "../components/PagedRecordList.vue";
import { useInvestorApi } from "../lib/api";
import { usePagedList } from "../lib/list";
import { formatDate } from "../lib/format";
import type { MarketDateListRow } from "../types";

const api = useInvestorApi();
const list = usePagedList<MarketDateListRow>({
	fetchPage: api.fetchMarketDates,
	sortBy: "date",
	errorMessage: "Market dates could not be loaded. Please retry.",
});
const { activeFilter, clearFilter } = list;
const sortColumns = [{ label: "Date", field: "date" }];
</script>

<template>
	<section class="record-surface" aria-label="Bond market date list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<PagedRecordList
			:list="list"
			:columns="['minmax(12rem,1fr)']"
			:sort-columns="sortColumns"
			row-test-id="market-date-row"
			loading-text="Loading market dates…"
			empty-text="No market dates match the selected filters."
			empty-test-id="market-dates-empty"
			pagination-label="Market date list pagination"
		>
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
		</PagedRecordList>
	</section>
</template>
