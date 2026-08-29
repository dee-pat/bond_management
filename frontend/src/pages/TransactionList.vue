<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import { fetchTransactions, InvestorApiError, redirectToLogin } from "../lib/api";
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
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchTransactions({
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
			<label class="portfolio-filter" for="transaction-portfolio-filter">
				<span>Portfolio Name</span>
				<select
					id="transaction-portfolio-filter"
					v-model="selectedPortfolio"
					:disabled="loading || !hasAssignments"
					@change="changePortfolio"
				>
					<option value="">All assigned portfolios</option>
					<option
						v-for="portfolio in bootstrap.portfolios"
						:key="portfolio.name"
						:value="portfolio.name"
					>
						{{ portfolio.label }}
					</option>
				</select>
			</label>
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
			<button class="secondary-button" type="button" @click="retryTransactions">
				Retry
			</button>
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
				<button class="secondary-button" type="button" @click="retryTransactions">
					Retry
				</button>
			</div>

			<div class="transaction-table-wrap">
				<table class="transaction-table">
					<thead>
						<tr>
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
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="transaction in transactions"
							:key="transaction.name"
							data-testid="transaction-row"
						>
							<td data-label="Settlement Date">
								<RouterLink
									:to="`/transactions/${encodeURIComponent(transaction.name)}`"
									:aria-label="`View transaction ${transaction.name}`"
								>
									{{ formatDate(transaction.settlement_date) }}
								</RouterLink>
							</td>
							<td data-label="Transaction Type">
								<button
									class="list-filter-button"
									type="button"
									:aria-label="`Filter Transaction Type by ${transaction.transaction_type}`"
									@click="
										applyFilter(
											'transaction_type',
											'Transaction Type',
											transaction.transaction_type
										)
									"
								>
									{{ transaction.transaction_type }}
								</button>
							</td>
							<td data-label="Portfolio Name">
								<button
									class="list-filter-button"
									type="button"
									:aria-label="`Filter Portfolio Name by ${transaction.portfolio_name}`"
									@click="
										applyFilter(
											'portfolio_name',
											'Portfolio Name',
											transaction.portfolio_name
										)
									"
								>
									{{ transaction.portfolio_name }}
								</button>
							</td>
							<td data-label="ISIN">
								<button
									class="list-filter-button"
									type="button"
									:aria-label="`Filter ISIN by ${transaction.isin}`"
									@click="applyFilter('isin', 'ISIN', transaction.isin)"
								>
									{{ transaction.isin }}
								</button>
							</td>
							<td data-label="Trade Date">
								<span>{{ formatDate(transaction.trade_date) }}</span>
							</td>
							<td data-label="Quantity/ Face Value">
								<button
									class="list-filter-button"
									type="button"
									:aria-label="`Filter Quantity/ Face Value by ${transaction.quantity_face_value}`"
									@click="
										applyFilter(
											'quantity_face_value',
											'Quantity/ Face Value',
											transaction.quantity_face_value
										)
									"
								>
									{{ formatNumber(transaction.quantity_face_value) }}
								</button>
							</td>
							<td data-label="Price">
								<button
									class="list-filter-button"
									type="button"
									:aria-label="`Filter Price by ${transaction.price}`"
									@click="applyFilter('price', 'Price', transaction.price)"
								>
									{{ formatNumber(transaction.price, 6) }}
								</button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

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
