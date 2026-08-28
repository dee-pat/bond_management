<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import { fetchStatements, InvestorApiError, redirectToLogin } from "../lib/api";
import { toFilterValue } from "../lib/list";
import { formatDate } from "../lib/format";
import type {
	ActiveListFilter,
	InvestorBootstrap,
	SortOrder,
	StatementListRow,
	StatementPage,
} from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const selectedPortfolio = ref("");
const selectedStatus = ref("");
const activeFilter = ref<ActiveListFilter | null>(null);
const sortBy = ref("statement_date");
const sortOrder = ref<SortOrder>("desc");
const statements = ref<StatementListRow[]>([]);
const pagination = ref<StatementPage["pagination"]>({
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
	if (selectedStatus.value) {
		filters.push({
			field: "reconciliation_status",
			label: "Reconciliation Status",
			value: selectedStatus.value,
		});
	}
	if (activeFilter.value) filters.push(activeFilter.value);
	return filters;
});

async function loadStatements(
	start = 0,
	append = false,
	pageLength = pagination.value.page_length
): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchStatements({
			portfolio: selectedPortfolio.value || undefined,
			reconciliationStatus: selectedStatus.value || undefined,
			start,
			pageLength,
			sortBy: sortBy.value || undefined,
			sortOrder: sortBy.value ? sortOrder.value : undefined,
			filterField: activeFilter.value?.field,
			filterValue: activeFilter.value?.value,
		});
		if (requestId !== latestRequest) return;
		statements.value = append ? [...statements.value, ...response.data] : response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) return;
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Statements could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) loading.value = false;
	}
}

function changeFilters(): void {
	void loadStatements(0);
}

function applyFilter(field: string, label: string, value: unknown): void {
	const filterValue = toFilterValue(value);
	if (!filterValue) return;
	if (field === "portfolio_name") selectedPortfolio.value = filterValue;
	else if (field === "reconciliation_status") selectedStatus.value = filterValue;
	else activeFilter.value = { field, label, value: filterValue };
	void loadStatements(0);
}

function clearFilter(field: string): void {
	if (field === "portfolio_name") selectedPortfolio.value = "";
	if (field === "reconciliation_status") selectedStatus.value = "";
	if (activeFilter.value?.field === field) activeFilter.value = null;
	void loadStatements(0);
}

function clearAllFilters(): void {
	selectedPortfolio.value = "";
	selectedStatus.value = "";
	activeFilter.value = null;
	void loadStatements(0);
}

function changeSort(field: string, order: SortOrder): void {
	sortBy.value = field;
	sortOrder.value = order;
	void loadStatements(0);
}

function loadMoreStatements(): void {
	void loadStatements(pagination.value.start + pagination.value.page_length, true);
}

function changePageLength(pageLength: number): void {
	if (pageLength === pagination.value.page_length) return;
	void loadStatements(0, false, pageLength);
}

function retryStatements(): void {
	void loadStatements(0, false);
}

onMounted(() => void loadStatements());
</script>

<template>
	<section class="record-surface" aria-label="Bond statement list">
		<div class="surface-heading surface-heading--filters">
			<div class="surface-filters">
				<label class="surface-filter" for="statement-portfolio-filter">
					<span>Portfolio Name</span>
					<select
						id="statement-portfolio-filter"
						v-model="selectedPortfolio"
						:disabled="loading || !hasAssignments"
						@change="changeFilters"
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

				<label class="surface-filter" for="statement-status-filter">
					<span>Reconciliation Status</span>
					<select
						id="statement-status-filter"
						v-model="selectedStatus"
						:disabled="loading || !hasAssignments"
						@change="changeFilters"
					>
						<option value="">All statuses</option>
						<option value="Matched">Matched</option>
						<option value="Mismatched">Mismatched</option>
					</select>
				</label>
			</div>
		</div>

		<ListFilterBar
			:filters="activeFilters"
			@clear="clearFilter"
			@clear-all="clearAllFilters"
		/>

		<div v-if="loading && statements.length === 0" class="surface-state" aria-live="polite">
			Loading statements…
		</div>

		<div
			v-else-if="error && statements.length === 0"
			class="surface-state surface-state--error"
			role="alert"
		>
			<p>{{ error }}</p>
			<button class="secondary-button" type="button" @click="retryStatements">Retry</button>
		</div>

		<div v-else-if="!hasAssignments" class="surface-state" data-testid="statements-empty">
			No portfolios are assigned to your account.
		</div>

		<div
			v-else-if="statements.length === 0"
			class="surface-state"
			data-testid="statements-empty"
		>
			No statements match the selected filters.
		</div>

		<template v-else>
			<div v-if="error" class="surface-state surface-state--error" role="alert">
				<p>{{ error }}</p>
				<button class="secondary-button" type="button" @click="retryStatements">
					Retry
				</button>
			</div>

			<div class="record-table-wrap">
				<table class="record-table">
					<thead>
						<tr>
							<SortableColumn
								label="Statement Date"
								field="statement_date"
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
								label="Reconciliation Status"
								field="reconciliation_status"
								:sort-by="sortBy"
								:sort-order="sortOrder"
								:disabled="loading"
								@sort="changeSort"
							/>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="statement in statements"
							:key="statement.name"
							data-testid="statement-row"
						>
							<td data-label="Statement Date">
								<RouterLink
									:to="`/statements/${encodeURIComponent(statement.name)}`"
									:aria-label="`View statement ${statement.name}`"
								>
									{{ formatDate(statement.statement_date) }}
								</RouterLink>
							</td>
							<td data-label="Portfolio Name">
								<button
									class="list-filter-button"
									type="button"
									:aria-label="`Filter Portfolio Name by ${statement.portfolio_name}`"
									@click="
										applyFilter(
											'portfolio_name',
											'Portfolio Name',
											statement.portfolio_name
										)
									"
								>
									{{ statement.portfolio_name }}
								</button>
							</td>
							<td data-label="Reconciliation Status">
								<button
									v-if="statement.reconciliation_status"
									class="status-badge list-filter-status"
									:class="`status-badge--${statement.reconciliation_status.toLowerCase()}`"
									type="button"
									:aria-label="`Filter Reconciliation Status by ${statement.reconciliation_status}`"
									@click="
										applyFilter(
											'reconciliation_status',
											'Reconciliation Status',
											statement.reconciliation_status
										)
									"
								>
									{{ statement.reconciliation_status }}
								</button>
								<span v-else class="status-badge status-badge--unset">—</span>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<ListPagination
				:has-more="pagination.has_more"
				:item-count="statements.length"
				:loading="loading"
				:page-length="pagination.page_length"
				label="Statement list pagination"
				@change-page-length="changePageLength"
				@load-more="loadMoreStatements"
			/>
		</template>
	</section>
</template>
