<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { Button, Select } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import SurfaceState from "../components/SurfaceState.vue";
import { useInvestorApi } from "../lib/api";
import { toFilterValue, usePagedList } from "../lib/list";
import { formatDate, formatNumber } from "../lib/format";
import type { ActiveListFilter, InvestorBootstrap, TransactionListRow } from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const api = useInvestorApi();
const selectedPortfolio = ref("");
const {
	rows: transactions,
	activeFilter,
	sortBy,
	sortOrder,
	pagination,
	loading,
	error,
	load: loadTransactions,
	changeSort,
	loadMore: loadMoreTransactions,
	changePageLength,
	retry: retryTransactions,
} = usePagedList<TransactionListRow>({
	fetchPage: (parameters) =>
		api.fetchTransactions({
			...parameters,
			portfolio: selectedPortfolio.value || undefined,
		}),
	sortBy: "settlement_date",
	errorMessage: "Transactions could not be loaded. Please retry.",
});

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

		<SurfaceState
			v-if="loading && transactions.length === 0"
			:loading="loading"
			loading-text="Loading transactions…"
		/>

		<SurfaceState
			v-else-if="error && transactions.length === 0"
			:error="error"
			@retry="retryTransactions"
		/>

		<div v-else-if="!hasAssignments" class="surface-state" data-testid="transactions-empty">
			No portfolios are assigned to your account.
		</div>

		<div
			v-else-if="transactions.length === 0"
			class="surface-state"
			data-testid="transactions-empty"
		>
			No transactions match the selected filters.
		</div>

		<template v-else>
			<SurfaceState v-if="error" :error="error" @retry="retryTransactions" />

			<DataList
				:items="transactions"
				:columns="[
					'minmax(9rem,1fr)',
					'minmax(8rem,1fr)',
					'minmax(12rem,1.4fr)',
					'minmax(9rem,1fr)',
					'minmax(9rem,1fr)',
					'minmax(10rem,1fr)',
					'minmax(8rem,1fr)',
				]"
				row-key="name"
				row-test-id="transaction-row"
			>
				<template #header>
					<SortableColumn
						label="Settlement Date"
						field="settlement_date"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Transaction Type"
						field="transaction_type"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Portfolio Name"
						field="portfolio_name"
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
						label="Trade Date"
						field="trade_date"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Quantity/ Face Value"
						field="quantity_face_value"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
					<SortableColumn
						label="Price"
						field="price"
						:sort-by="sortBy"
						:sort-order="sortOrder"
						:disabled="loading"
						@sort="changeSort"
					/>
				</template>
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
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Transaction Type by ${transaction.transaction_type}`"
							@click="
								applyFilter(
									'transaction_type',
									'Transaction Type',
									transaction.transaction_type
								)
							"
						>
							{{ transaction.transaction_type }}
						</Button>
					</ListCell>
					<ListCell data-label="Portfolio Name">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Portfolio Name by ${transaction.portfolio_name}`"
							@click="
								applyFilter(
									'portfolio_name',
									'Portfolio Name',
									transaction.portfolio_name
								)
							"
						>
							{{ transaction.portfolio_name }}
						</Button>
					</ListCell>
					<ListCell data-label="ISIN">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter ISIN by ${transaction.isin}`"
							@click="applyFilter('isin', 'ISIN', transaction.isin)"
						>
							{{ transaction.isin }}
						</Button>
					</ListCell>
					<ListCell data-label="Trade Date">
						<span>{{ formatDate(transaction.trade_date) }}</span>
					</ListCell>
					<ListCell data-label="Quantity/ Face Value">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Quantity/ Face Value by ${transaction.quantity_face_value}`"
							@click="
								applyFilter(
									'quantity_face_value',
									'Quantity/ Face Value',
									transaction.quantity_face_value
								)
							"
						>
							{{ formatNumber(transaction.quantity_face_value) }}
						</Button>
					</ListCell>
					<ListCell data-label="Price">
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Price by ${transaction.price}`"
							@click="applyFilter('price', 'Price', transaction.price)"
						>
							{{ formatNumber(transaction.price, 6) }}
						</Button>
					</ListCell>
				</template>
			</DataList>

			<ListPagination
				:has-more="pagination.has_more"
				:item-count="transactions.length"
				:loading="loading"
				:page-length="pagination.page_length"
				label="Transaction list pagination"
				@change-page-length="changePageLength"
				@load-more="loadMoreTransactions"
			/>
		</template>
	</section>
</template>
