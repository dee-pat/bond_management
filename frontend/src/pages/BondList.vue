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
import type { BondListRow } from "../types";

const api = useInvestorApi();
const {
	rows: bonds,
	activeFilter,
	sortBy,
	sortOrder,
	pagination,
	loading,
	error,
	applyFilter,
	clearFilter,
	changeSort,
	loadMore: loadMoreBonds,
	changePageLength,
	retry: retryBonds,
} = usePagedList<BondListRow>({
	fetchPage: api.fetchBonds,
	sortBy: "issue_date",
	errorMessage: "Bonds could not be loaded. Please retry.",
});
</script>

<template>
	<section class="record-surface" aria-label="Bond master list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<SurfaceState
			v-if="loading && bonds.length === 0"
			:loading="loading"
			loading-text="Loading bonds…"
		/>

		<SurfaceState v-else-if="error && bonds.length === 0" :error="error" @retry="retryBonds" />

		<div v-else-if="bonds.length === 0" class="surface-state" data-testid="bonds-empty">
			No bonds match the selected filters.
		</div>

		<template v-else>
			<SurfaceState v-if="error" :error="error" @retry="retryBonds" />

			<DataList
				:items="bonds"
				:columns="['minmax(12rem,1.4fr)', 'minmax(9rem,1fr)', '8rem', '9rem']"
				row-key="name"
				row-test-id="bond-row"
			>
				<template #header>
					<SortableColumn
						label="Bond Name"
						field="bond_name"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="ISIN"
						field="isin"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Currency"
						field="currency"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Issue Date"
						field="issue_date"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
				</template>
				<template #row="{ item: bond }">
					<ListCell data-label="Bond Name">
						<RouterLink
							:to="`/bonds/${encodeURIComponent(bond.name)}`"
							:aria-label="`View bond ${bond.name}`"
						>
							{{ bond.bond_name }}
						</RouterLink>
					</ListCell>
					<ListCell data-label="ISIN">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter ISIN by ${bond.isin}`"
							@click="applyFilter('isin', 'ISIN', bond.isin)"
						>
							{{ bond.isin }}
						</Button>
					</ListCell>
					<ListCell data-label="Currency">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Currency by ${bond.currency}`"
							@click="applyFilter('currency', 'Currency', bond.currency)"
						>
							{{ bond.currency }}
						</Button>
					</ListCell>
					<ListCell data-label="Issue Date">
						<span>{{ formatDate(bond.issue_date) }}</span>
					</ListCell>
				</template>
			</DataList>

			<ListPagination
				:has-more="pagination.has_more"
				:item-count="bonds.length"
				:loading="loading"
				:page-length="pagination.page_length"
				label="Bond list pagination"
				@change-page-length="changePageLength"
				@load-more="loadMoreBonds"
			/>
		</template>
	</section>
</template>
