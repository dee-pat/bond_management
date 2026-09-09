<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { Button } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import ListFilterBar from "../components/ListFilterBar.vue";
import ListPagination from "../components/ListPagination.vue";
import SortableColumn from "../components/SortableColumn.vue";
import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import { toFilterValue } from "../lib/list";
import { formatDate } from "../lib/format";
import type { ActiveListFilter, BondListRow, BondPage, SortOrder } from "../types";

const bonds = ref<BondListRow[]>([]);
const activeFilter = ref<ActiveListFilter | null>(null);
const sortBy = ref("issue_date");
const sortOrder = ref<SortOrder>("desc");
const pagination = ref<BondPage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
const api = useInvestorApi();
let latestRequest = 0;

async function loadBonds(
	start = 0,
	append = false,
	pageLength = pagination.value.page_length
): Promise<void> {
	if (append && (loading.value || !pagination.value.has_more)) return;

	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;
	if (!append) {
		bonds.value = [];
		pagination.value = { start: 0, page_length: pageLength, has_more: false };
	}

	try {
		const response = await api.fetchBonds({
			start,
			pageLength,
			sortBy: sortBy.value || undefined,
			sortOrder: sortBy.value ? sortOrder.value : undefined,
			filterField: activeFilter.value?.field,
			filterValue: activeFilter.value?.value,
		});
		if (requestId !== latestRequest) return;
		bonds.value = append ? [...bonds.value, ...response.data] : response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) return;
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Bonds could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) loading.value = false;
	}
}

function applyFilter(field: string, label: string, value: unknown): void {
	const filterValue = toFilterValue(value);
	if (!filterValue) return;
	activeFilter.value = { field, label, value: filterValue };
	void loadBonds(0);
}

function clearFilter(): void {
	activeFilter.value = null;
	void loadBonds(0);
}

function changeSort(field: string, order: SortOrder): void {
	sortBy.value = field;
	sortOrder.value = order;
	void loadBonds(0);
}

function loadMoreBonds(): void {
	void loadBonds(pagination.value.start + pagination.value.page_length, true);
}

function changePageLength(pageLength: number): void {
	if (pageLength === pagination.value.page_length) return;
	void loadBonds(0, false, pageLength);
}

function retryBonds(): void {
	void loadBonds(0, false);
}

onMounted(() => void loadBonds());
</script>

<template>
	<section class="record-surface" aria-label="Bond master list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<div v-if="loading && bonds.length === 0" class="surface-state" aria-live="polite">
			Loading bonds…
		</div>

		<div
			v-else-if="error && bonds.length === 0"
			class="surface-state surface-state--error"
			role="alert"
		>
			<p>{{ error }}</p>
			<Button label="Retry" variant="outline" @click="retryBonds" />
		</div>

		<div v-else-if="bonds.length === 0" class="surface-state" data-testid="bonds-empty">
			No bonds match the selected filters.
		</div>

		<template v-else>
			<div v-if="error" class="surface-state surface-state--error" role="alert">
				<p>{{ error }}</p>
				<Button label="Retry" variant="outline" @click="retryBonds" />
			</div>

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
