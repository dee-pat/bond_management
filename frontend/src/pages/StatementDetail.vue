<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { fetchStatement, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate, formatNumber } from "../lib/format";
import type { StatementDetail } from "../types";

const route = useRoute();
const statement = ref<StatementDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const statementName = computed(() => String(route.params.statementName ?? ""));
let latestRequest = 0;

function formatMarketPrice(value: number | null): string {
	return value === null ? "—" : formatNumber(value, 6);
}

async function loadStatement(): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchStatement(statementName.value);
		if (requestId === latestRequest) {
			statement.value = response.statement;
		}
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value =
			caughtError instanceof InvestorApiError && caughtError.status === 403
				? "This statement is unavailable or you do not have permission to view it."
				: "The statement could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

onMounted(() => void loadStatement());
</script>

<template>
	<section class="record-surface" aria-labelledby="statement-detail-title">
		<RouterLink class="back-link" to="/statements"> ← Back to statements </RouterLink>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading statement…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button class="secondary-button" type="button" @click="loadStatement">Retry</button>
		</div>

		<template v-else-if="statement">
			<div class="surface-heading">
				<div>
					<p class="surface-kicker">Statement date</p>
					<h2 id="statement-detail-title">
						{{ formatDate(statement.statement_date) }}
					</h2>
				</div>
				<span class="read-only-badge">Read only</span>
			</div>

			<dl class="record-detail-grid" data-testid="statement-detail">
				<div>
					<dt>Portfolio Name</dt>
					<dd>{{ statement.portfolio_name }}</dd>
				</div>
				<div>
					<dt>Statement Date</dt>
					<dd>{{ formatDate(statement.statement_date) }}</dd>
				</div>
				<div>
					<dt>Market Price Posting</dt>
					<dd>{{ statement.market_price_posting || "—" }}</dd>
				</div>
				<div>
					<dt>Reconciliation Status</dt>
					<dd>{{ statement.reconciliation_status || "—" }}</dd>
				</div>
			</dl>

			<div class="holding-section">
				<h3>Bond Statement Details</h3>
				<div v-if="statement.bond_statement_details.length === 0" class="surface-state">
					This statement has no bond holdings.
				</div>
				<div v-else class="record-table-wrap">
					<table class="record-table" data-testid="statement-holdings">
						<thead>
							<tr>
								<th scope="col">ISIN</th>
								<th scope="col">Quantity</th>
								<th scope="col">Principal Factor</th>
								<th scope="col">Market Price</th>
								<th scope="col">Currency</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="holding in statement.bond_statement_details"
								:key="holding.isin"
							>
								<td data-label="ISIN">
									{{ holding.isin }}
								</td>
								<td data-label="Quantity">
									{{ formatNumber(holding.quantity) }}
								</td>
								<td data-label="Principal Factor">
									{{ formatNumber(holding.principal_factor, 6) }}
								</td>
								<td data-label="Market Price">
									{{ formatMarketPrice(holding.market_price) }}
								</td>
								<td data-label="Currency">
									{{ holding.currency }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</template>
	</section>
</template>
