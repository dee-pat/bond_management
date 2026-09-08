<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { Button, Select } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import { toFilterValue } from "../lib/list";
import { formatDate, formatNumber } from "../lib/format";
import type {
	ActiveListFilter,
	InvestorBootstrap,
	SortOrder,
	TransactionListRow,
	TransactionPage,
} from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const api = useInvestorApi();
const selectedPortfolio = ref("");
const activeFilter = ref<ActiveListFilter | null>(null);
const sortBy = ref("settlement_date");
const sortOrder = ref<SortOrder>("desc");
const transactions = ref<TransactionListRow[]>([]);
const pagination = ref<TransactionPage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
let latestRequest = 0;

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

async function loadTransactions(
	start = 0,
	append = false,
	pageLength = pagination.value.page_length
): Promise<void> {
	if (append && (loading.value || !pagination.value.has_more)) return;

	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;
	if (!append) {
		transactions.value = [];
		pagination.value = { start: 0, page_length: pageLength, has_more: false };
	}

	try {
		const response = await api.fetchTransactions({
			portfolio: selectedPortfolio.value || undefined,
			start,
			pageLength,
			sortBy: sortBy.value || undefined,
			sortOrder: sortBy.value ? sortOrder.value : undefined,
			filterField: activeFilter.value?.field,
			filterValue: activeFilter.value?.value,
		});
		if (requestId !== latestRequest) return;
		transactions.value = append ? [...transactions.value, ...response.data] : response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) return;
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Transactions could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) loading.value = false;
	}
}

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

function changeSort(field: string, order: SortOrder): void {
	sortBy.value = field;
	sortOrder.value = order;
	void loadTransactions(0);
}

function loadMoreTransactions(): void {
	void loadTransactions(pagination.value.start + pagination.value.page_length, true);
}

function changePageLength(pageLength: number): void {
	if (pageLength === pagination.value.page_length) return;
	void loadTransactions(0, false, pageLength);
}

function retryTransactions(): void {
	void loadTransactions(0, false);
}

onMounted(() => void loadTransactions());
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

		<div v-if="loading && transactions.length === 0" class="surface-state" aria-live="polite">
			Loading transactions…
		</div>

		<div
			v-else-if="error && transactions.length === 0"
			class="surface-state surface-state--error"
			role="alert"
		>
			<p>{{ error }}</p>
			<Button label="Retry" variant="outline" @click="retryTransactions" />
		</div>

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
			<div v-if="error" class="surface-state surface-state--error" role="alert">
				<p>{{ error }}</p>
				<Button label="Retry" variant="outline" @click="retryTransactions" />
			</div>

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
