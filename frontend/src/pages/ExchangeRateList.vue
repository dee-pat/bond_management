<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { fetchExchangeRates, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate, formatNumber } from "../lib/format";
import type { ExchangeRateListRow, ExchangeRatePage } from "../types";

const exchangeRates = ref<ExchangeRateListRow[]>([]);
const pagination = ref<ExchangeRatePage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
let latestRequest = 0;

async function loadExchangeRates(start = 0): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchExchangeRates({
			start,
			pageLength: pagination.value.page_length,
		});
		if (requestId !== latestRequest) {
			return;
		}
		exchangeRates.value = response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Exchange rates could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

onMounted(() => void loadExchangeRates());
</script>

<template>
	<section class="record-surface" aria-labelledby="exchange-rate-list-title">
		<div class="surface-heading">
			<div>
				<p class="surface-kicker">Shared reference history</p>
				<h2 id="exchange-rate-list-title">Exchange rate history</h2>
			</div>
		</div>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading exchange rates…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button
				class="secondary-button"
				type="button"
				@click="loadExchangeRates(pagination.start)"
			>
				Retry
			</button>
		</div>

		<div
			v-else-if="exchangeRates.length === 0"
			class="surface-state"
			data-testid="exchange-rates-empty"
		>
			No exchange rates are available.
		</div>

		<template v-else>
			<div class="record-table-wrap">
				<table class="record-table">
					<thead>
						<tr>
							<th scope="col">Rate Date</th>
							<th scope="col">From Currency</th>
							<th scope="col">To Currency</th>
							<th scope="col">Rate</th>
							<th scope="col">Reverse Rate</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="exchangeRate in exchangeRates"
							:key="exchangeRate.name"
							data-testid="exchange-rate-row"
						>
							<td data-label="Rate Date">
								{{ formatDate(exchangeRate.rate_date) }}
							</td>
							<td data-label="From Currency">
								<RouterLink
									:to="`/exchange-rates/${encodeURIComponent(
										exchangeRate.name
									)}`"
									:aria-label="`View exchange rate ${exchangeRate.name}`"
								>
									{{ exchangeRate.from_currency }}
								</RouterLink>
								<small>{{ exchangeRate.name }}</small>
							</td>
							<td data-label="To Currency">
								{{ exchangeRate.to_currency }}
							</td>
							<td data-label="Rate">
								{{ formatNumber(exchangeRate.rate, 12) }}
							</td>
							<td data-label="Reverse Rate">
								{{ formatNumber(exchangeRate.reverse_rate, 12) }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div class="pagination-controls" aria-label="Exchange rate pages">
				<button
					class="secondary-button"
					type="button"
					:disabled="pagination.start === 0"
					@click="
						loadExchangeRates(Math.max(0, pagination.start - pagination.page_length))
					"
				>
					Previous
				</button>
				<span>
					{{ pagination.start + 1 }}–{{ pagination.start + exchangeRates.length }}
				</span>
				<button
					class="secondary-button"
					type="button"
					:disabled="!pagination.has_more"
					@click="loadExchangeRates(pagination.start + pagination.page_length)"
				>
					Next
				</button>
			</div>
		</template>
	</section>
</template>
