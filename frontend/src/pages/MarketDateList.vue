<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { fetchMarketDates, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate } from "../lib/format";
import type { MarketDateListRow, MarketDatePage } from "../types";

const marketDates = ref<MarketDateListRow[]>([]);
const pagination = ref<MarketDatePage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
let latestRequest = 0;

async function loadMarketDates(start = 0): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchMarketDates({
			start,
			pageLength: pagination.value.page_length,
		});
		if (requestId !== latestRequest) {
			return;
		}
		marketDates.value = response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Market dates could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

onMounted(() => void loadMarketDates());
</script>

<template>
	<section class="record-surface" aria-labelledby="market-date-list-title">
		<div class="surface-heading">
			<div>
				<p class="surface-kicker">Shared market history</p>
				<h2 id="market-date-list-title">Market dates</h2>
			</div>
		</div>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading market dates…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button
				class="secondary-button"
				type="button"
				@click="loadMarketDates(pagination.start)"
			>
				Retry
			</button>
		</div>

		<div
			v-else-if="marketDates.length === 0"
			class="surface-state"
			data-testid="market-dates-empty"
		>
			No market dates are available.
		</div>

		<template v-else>
			<div class="record-table-wrap">
				<table class="record-table">
					<thead>
						<tr>
							<th scope="col">Date</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="marketDate in marketDates"
							:key="marketDate.name"
							data-testid="market-date-row"
						>
							<td data-label="Date">
								<RouterLink
									:to="`/market-dates/${encodeURIComponent(marketDate.name)}`"
									:aria-label="`View market date ${marketDate.name}`"
								>
									{{ formatDate(marketDate.date) }}
								</RouterLink>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div class="pagination-controls" aria-label="Market date pages">
				<button
					class="secondary-button"
					type="button"
					:disabled="pagination.start === 0"
					@click="
						loadMarketDates(Math.max(0, pagination.start - pagination.page_length))
					"
				>
					Previous
				</button>
				<span>{{ pagination.start + 1 }}–{{ pagination.start + marketDates.length }}</span>
				<button
					class="secondary-button"
					type="button"
					:disabled="!pagination.has_more"
					@click="loadMarketDates(pagination.start + pagination.page_length)"
				>
					Next
				</button>
			</div>
		</template>
	</section>
</template>
