<script setup lang="ts">
import { RouterLink } from "vue-router";
import { ListCell } from "frappe-ui/list";

import ListFilterBar from "../components/ListFilterBar.vue";
import PagedRecordList from "../components/PagedRecordList.vue";
import FilterButton from "../components/FilterButton.vue";
import { useInvestorApi } from "../lib/api";
import { usePagedList } from "../lib/list";
import { formatDate } from "../lib/format";
import type { BondListRow } from "../types";

const api = useInvestorApi();
const list = usePagedList<BondListRow>({
	fetchPage: api.fetchBonds,
	sortBy: "issue_date",
	errorMessage: "Bonds could not be loaded. Please retry.",
});
const { activeFilter, applyFilter, clearFilter } = list;
const sortColumns = [
	{ label: "Bond Name", field: "bond_name" },
	{ label: "ISIN", field: "isin" },
	{ label: "Currency", field: "currency" },
	{ label: "Issue Date", field: "issue_date" },
];
</script>

<template>
	<section class="record-surface" aria-label="Bond master list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<PagedRecordList
			:list="list"
			:columns="['minmax(12rem,1.4fr)', 'minmax(9rem,1fr)', '8rem', '9rem']"
			:sort-columns="sortColumns"
			row-test-id="bond-row"
			loading-text="Loading bonds…"
			empty-text="No bonds match the selected filters."
			empty-test-id="bonds-empty"
			pagination-label="Bond list pagination"
		>
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
					<FilterButton
						field="isin"
						label="ISIN"
						:value="bond.isin"
						@filter="applyFilter"
					/>
				</ListCell>
				<ListCell data-label="Currency">
					<FilterButton
						field="currency"
						label="Currency"
						:value="bond.currency"
						@filter="applyFilter"
					/>
				</ListCell>
				<ListCell data-label="Issue Date">
					<span>{{ formatDate(bond.issue_date) }}</span>
				</ListCell>
			</template>
		</PagedRecordList>
	</section>
</template>
