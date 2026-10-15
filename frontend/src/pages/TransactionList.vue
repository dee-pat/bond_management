<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { Select } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import ListFilterBar from "../components/ListFilterBar.vue";
import PagedRecordList from "../components/PagedRecordList.vue";
import FilterButton from "../components/FilterButton.vue";
import { useInvestorApi } from "../lib/api";
import { toFilterValue, usePagedList } from "../lib/list";
import { formatDate, formatNumber } from "../lib/format";
import type { ActiveListFilter, InvestorBootstrap, TransactionListRow } from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const api = useInvestorApi();
const selectedPortfolio = ref("");
const list = usePagedList<TransactionListRow>({
	fetchPage: (parameters) =>
		api.fetchTransactions({
			...parameters,
			portfolio: selectedPortfolio.value || undefined,
		}),
	sortBy: "settlement_date",
	errorMessage: "Transactions could not be loaded. Please retry.",
});
const { activeFilter, loading, load: loadTransactions } = list;

const hasAssignments = computed(() => props.bootstrap.portfolios.length > 0);
const portfolioOptions = computed(() => [
	{ label: "All assigned portfolios", value: "" },
	...props.bootstrap.portfolios.map((portfolio) => ({
		label: portfolio.label,
		value: portfolio.name,
	})),
]);
const activeFilters = computed<ActiveListFilter[]>(() => {
	const filters: ActiveListFilter[] = [];
	if (selectedPortfolio.value) {
		const portfolio = props.bootstrap.portfolios.find(
			(choice) => choice.name === selectedPortfolio.value
		);
		filters.push({
			field: "portfolio_name",
			label: "Portfolio Name",
			value: portfolio?.label ?? selectedPortfolio.value,
		});
	}
	if (activeFilter.value) filters.push(activeFilter.value);
	return filters;
});

function changePortfolio(): void {
	void loadTransactions(0);
}

function applyFilter(field: string, label: string, value: unknown): void {
	const filterValue = toFilterValue(value);
	if (!filterValue) return;
	if (field === "portfolio_name") {
		selectedPortfolio.value = filterValue;
	} else {
		activeFilter.value = { field, label, value: filterValue };
	}
	void loadTransactions(0);
}

function clearFilter(field: string): void {
	if (field === "portfolio_name") selectedPortfolio.value = "";
	if (activeFilter.value?.field === field) activeFilter.value = null;
	void loadTransactions(0);
}

function clearAllFilters(): void {
	selectedPortfolio.value = "";
	activeFilter.value = null;
	void loadTransactions(0);
}
const sortColumns = [
	{ label: "Settlement Date", field: "settlement_date" },
	{ label: "Transaction Type", field: "transaction_type" },
	{ label: "Portfolio Name", field: "portfolio_name" },
	{ label: "ISIN", field: "isin" },
	{ label: "Trade Date", field: "trade_date" },
	{ label: "Quantity/ Face Value", field: "quantity_face_value" },
	{ label: "Price", field: "price" },
];
</script>

<template>
	<section class="transaction-surface" aria-label="Bond transaction list">
		<div class="surface-heading surface-heading--filters">
			<Select
				id="transaction-portfolio-filter"
				v-model="selectedPortfolio"
				class="portfolio-filter"
				label="Portfolio Name"
				:options="portfolioOptions"
				:disabled="loading || !hasAssignments"
				@update:model-value="changePortfolio"
			/>
		</div>

		<ListFilterBar
			:filters="activeFilters"
			@clear="clearFilter"
			@clear-all="clearAllFilters"
		/>

		<PagedRecordList
			:list="list"
			:columns="[
				'minmax(9rem,1fr)',
				'minmax(8rem,1fr)',
				'minmax(12rem,1.4fr)',
				'minmax(9rem,1fr)',
				'minmax(9rem,1fr)',
				'minmax(10rem,1fr)',
				'minmax(8rem,1fr)',
			]"
			:sort-columns="sortColumns"
			row-test-id="transaction-row"
			loading-text="Loading transactions…"
			empty-text="No transactions match the selected filters."
			empty-test-id="transactions-empty"
			pagination-label="Transaction list pagination"
			:unassigned="!hasAssignments"
		>
			<template #row="{ item: transaction }">
				<ListCell data-label="Settlement Date">
					<RouterLink
						:to="`/transactions/${encodeURIComponent(transaction.name)}`"
						:aria-label="`View transaction ${transaction.name}`"
					>
						{{ formatDate(transaction.settlement_date) }}
					</RouterLink>
				</ListCell>
				<ListCell data-label="Transaction Type">
					<FilterButton
						field="transaction_type"
						label="Transaction Type"
						:value="transaction.transaction_type"
						@filter="applyFilter"
					/>
				</ListCell>
				<ListCell data-label="Portfolio Name">
					<FilterButton
						field="portfolio_name"
						label="Portfolio Name"
						:value="transaction.portfolio_name"
						@filter="applyFilter"
					/>
				</ListCell>
				<ListCell data-label="ISIN">
					<FilterButton
						field="isin"
						label="ISIN"
						:value="transaction.isin"
						@filter="applyFilter"
					/>
				</ListCell>
				<ListCell data-label="Trade Date">
					<span>{{ formatDate(transaction.trade_date) }}</span>
				</ListCell>
				<ListCell data-label="Quantity/ Face Value">
					<FilterButton
						field="quantity_face_value"
						label="Quantity/ Face Value"
						:value="transaction.quantity_face_value"
						@filter="applyFilter"
					>
						{{ formatNumber(transaction.quantity_face_value) }}
					</FilterButton>
				</ListCell>
				<ListCell data-label="Price">
					<FilterButton
						field="price"
						label="Price"
						:value="transaction.price"
						@filter="applyFilter"
					>
						{{ formatNumber(transaction.price, 6) }}
					</FilterButton>
				</ListCell>
			</template>
		</PagedRecordList>
	</section>
</template>
