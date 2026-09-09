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
import { formatDate } from "../lib/format";
import type {
	ActiveListFilter,
	InvestorBootstrap,
	SortOrder,
	StatementListRow,
	StatementPage,
} from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const api = useInvestorApi();
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
const portfolioOptions = computed(() => [
	{ label: "All assigned portfolios", value: "" },
	...props.bootstrap.portfolios.map((portfolio) => ({
		label: portfolio.label,
		value: portfolio.name,
	})),
]);
const statusOptions = [
	{ label: "All statuses", value: "" },
	{ label: "Matched", value: "Matched" },
	{ label: "Mismatched", value: "Mismatched" },
];
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
	if (append && (loading.value || !pagination.value.has_more)) return;

	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;
	if (!append) {
		statements.value = [];
		pagination.value = { start: 0, page_length: pageLength, has_more: false };
	}

	try {
		const response = await api.fetchStatements({
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
				<Select
					id="statement-portfolio-filter"
					v-model="selectedPortfolio"
					class="surface-filter"
					label="Portfolio Name"
					:options="portfolioOptions"
					:disabled="loading || !hasAssignments"
					@update:model-value="changeFilters"
				/>

				<Select
					id="statement-status-filter"
					v-model="selectedStatus"
					class="surface-filter"
					label="Reconciliation Status"
					:options="statusOptions"
					:disabled="loading || !hasAssignments"
					@update:model-value="changeFilters"
				/>
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
			<Button label="Retry" variant="outline" @click="retryStatements" />
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
				<Button label="Retry" variant="outline" @click="retryStatements" />
			</div>

			<DataList
				:items="statements"
				:columns="['minmax(9rem,1fr)', 'minmax(12rem,1.4fr)', 'minmax(12rem,1fr)']"
				row-key="name"
				row-test-id="statement-row"
			>
				<template #header>
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
				</template>
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
						<Button
							class="list-filter-button"
							variant="ghost"
							size="sm"
							:label="`Filter Portfolio Name by ${statement.portfolio_name}`"
							@click="
								applyFilter(
									'portfolio_name',
									'Portfolio Name',
									statement.portfolio_name
								)
							"
						>
							{{ statement.portfolio_name }}
						</Button>
					</ListCell>
					<ListCell data-label="Reconciliation Status">
						<Button
							v-if="statement.reconciliation_status"
							class="status-badge list-filter-status"
							:class="`status-badge--${statement.reconciliation_status.toLowerCase()}`"
							variant="ghost"
							size="sm"
							:label="`Filter Reconciliation Status by ${statement.reconciliation_status}`"
							@click="
								applyFilter(
									'reconciliation_status',
									'Reconciliation Status',
									statement.reconciliation_status
								)
							"
						>
							{{ statement.reconciliation_status }}
						</Button>
						<span v-else class="status-badge status-badge--unset">—</span>
					</ListCell>
				</template>
			</DataList>

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
