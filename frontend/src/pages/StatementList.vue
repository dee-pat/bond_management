<script setup lang="ts">
import { ref } from "vue";
import { RouterLink } from "vue-router";
import { Badge, Button, Select } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import ListFilterBar from "../components/ListFilterBar.vue";
import PagedRecordList from "../components/PagedRecordList.vue";
import FilterButton from "../components/FilterButton.vue";
import { useInvestorApi } from "../lib/api";
import { usePagedList } from "../lib/list";
import { useListFilters, usePortfolioFilter } from "../lib/list-filters";
import { formatDate } from "../lib/format";
import type { InvestorBootstrap, StatementListRow } from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const api = useInvestorApi();
const {
	selected: selectedPortfolio,
	hasAssignments,
	options: portfolioOptions,
	filter: portfolioFilter,
} = usePortfolioFilter(() => props.bootstrap.portfolios);
const selectedStatus = ref("");
const list = usePagedList<StatementListRow>({
	fetchPage: (parameters) =>
		api.fetchStatements({
			...parameters,
			portfolio: selectedPortfolio.value || undefined,
			reconciliationStatus: selectedStatus.value || undefined,
		}),
	sortBy: "statement_date",
	errorMessage: "Statements could not be loaded. Please retry.",
});
const { loading } = list;
const { activeFilters, reload, applyFilter, clearFilter, clearAllFilters } = useListFilters(list, [
	portfolioFilter,
	{ field: "reconciliation_status", label: "Reconciliation Status", selected: selectedStatus },
]);

const statusOptions = [
	{ label: "All statuses", value: "" },
	{ label: "Matched", value: "Matched" },
	{ label: "Mismatched", value: "Mismatched" },
];
const sortColumns = [
	{ label: "Statement Date", field: "statement_date" },
	{ label: "Portfolio Name", field: "portfolio_name" },
	{ label: "Reconciliation Status", field: "reconciliation_status" },
];
</script>

<template>
	<section class="record-surface" aria-label="Bond statement list">
		<div class="surface-heading surface-heading--filters">
			<div class="surface-filters">
				<Select
					id="statement-portfolio-filter"
					v-model="selectedPortfolio"
					class="surface-filter"
					label="Portfolio Name"
					:options="portfolioOptions"
					:disabled="loading || !hasAssignments"
					@update:model-value="reload"
				/>

				<Select
					id="statement-status-filter"
					v-model="selectedStatus"
					class="surface-filter"
					label="Reconciliation Status"
					:options="statusOptions"
					:disabled="loading || !hasAssignments"
					@update:model-value="reload"
				/>
			</div>
		</div>

		<ListFilterBar
			:filters="activeFilters"
			@clear="clearFilter"
			@clear-all="clearAllFilters"
		/>

		<PagedRecordList
			:list="list"
			:columns="['minmax(9rem,1fr)', 'minmax(12rem,1.4fr)', 'minmax(12rem,1fr)']"
			:sort-columns="sortColumns"
			row-test-id="statement-row"
			loading-text="Loading statements…"
			empty-text="No statements match the selected filters."
			empty-test-id="statements-empty"
			pagination-label="Statement list pagination"
			:unassigned="!hasAssignments"
		>
			<template #row="{ item: statement }">
				<ListCell data-label="Statement Date">
					<RouterLink
						:to="`/statements/${encodeURIComponent(statement.name)}`"
						:aria-label="`View statement ${statement.name}`"
					>
						{{ formatDate(statement.statement_date) }}
					</RouterLink>
				</ListCell>
				<ListCell data-label="Portfolio Name">
					<FilterButton
						field="portfolio_name"
						label="Portfolio Name"
						:value="statement.portfolio_name"
						@filter="applyFilter"
					/>
				</ListCell>
				<ListCell data-label="Reconciliation Status">
					<Button
						v-if="statement.reconciliation_status"
						:theme="statement.reconciliation_status === 'Matched' ? 'green' : 'red'"
						variant="subtle"
						size="xs"
						:label="`Filter Reconciliation Status by ${statement.reconciliation_status}`"
						@click="
							applyFilter(
								'reconciliation_status',
								'Reconciliation Status',
								statement.reconciliation_status
							)
						"
					>
						<template #prefix>
							<span class="size-1.5 rounded-full bg-current" aria-hidden="true" />
						</template>
						{{ statement.reconciliation_status }}
					</Button>
					<Badge v-else theme="gray" variant="subtle" size="sm">—</Badge>
				</ListCell>
			</template>
		</PagedRecordList>
	</section>
</template>
