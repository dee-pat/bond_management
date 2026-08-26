<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { fetchStatements, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate } from "../lib/format";
import type { InvestorBootstrap, StatementListRow, StatementPage } from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const selectedPortfolio = ref("");
const selectedStatus = ref("");
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

async function loadStatements(start = 0): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchStatements({
			portfolio: selectedPortfolio.value || undefined,
			reconciliationStatus: selectedStatus.value || undefined,
			start,
			pageLength: pagination.value.page_length,
		});
		if (requestId !== latestRequest) {
			return;
		}
		statements.value = response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Statements could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

function changeFilters(): void {
	void loadStatements(0);
}

onMounted(() => void loadStatements());
</script>

<template>
	<section class="record-surface" aria-labelledby="statement-list-title">
		<div class="surface-heading">
			<div>
				<p class="surface-kicker">Assigned records</p>
				<h2 id="statement-list-title">Statement history</h2>
			</div>

			<div class="surface-filters">
				<label class="surface-filter">
					<span>Portfolio Name</span>
					<select
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

				<label class="surface-filter">
					<span>Reconciliation Status</span>
					<select
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

		<div v-if="loading" class="surface-state" aria-live="polite">Loading statements…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button
				class="secondary-button"
				type="button"
				@click="loadStatements(pagination.start)"
			>
				Retry
			</button>
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
			<div class="record-table-wrap">
				<table class="record-table">
					<thead>
						<tr>
							<th scope="col">Statement Date</th>
							<th scope="col">Portfolio Name</th>
							<th scope="col">Reconciliation Status</th>
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
								<small>{{ statement.name }}</small>
							</td>
							<td data-label="Portfolio Name">
								{{ statement.portfolio_name }}
							</td>
							<td data-label="Reconciliation Status">
								<span
									class="status-badge"
									:class="`status-badge--${
										statement.reconciliation_status?.toLowerCase() || 'unset'
									}`"
								>
									{{ statement.reconciliation_status || "—" }}
								</span>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div class="pagination-controls" aria-label="Statement pages">
				<button
					class="secondary-button"
					type="button"
					:disabled="pagination.start === 0"
					@click="loadStatements(Math.max(0, pagination.start - pagination.page_length))"
				>
					Previous
				</button>
				<span>{{ pagination.start + 1 }}–{{ pagination.start + statements.length }}</span>
				<button
					class="secondary-button"
					type="button"
					:disabled="!pagination.has_more"
					@click="loadStatements(pagination.start + pagination.page_length)"
				>
					Next
				</button>
			</div>
		</template>
	</section>
</template>
