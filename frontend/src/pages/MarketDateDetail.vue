<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { Button } from "frappe-ui";
import { ListCell, ListHeaderCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import { formatDate, formatNumber, formatPercent } from "../lib/format";
import type { MarketDateDetail } from "../types";
import YieldCurveChart from "./YieldCurveChart.vue";

const route = useRoute();
const marketDate = ref<MarketDateDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const marketDateName = computed(() => String(route.params.marketDateName ?? ""));
const api = useInvestorApi();
let latestRequest = 0;

async function loadMarketDate(): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await api.fetchMarketDate(marketDateName.value);
		if (requestId === latestRequest) {
			marketDate.value = response.market_date;
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
				? "This market date is unavailable or you do not have permission to view it."
				: "The market date could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

function formatOptionalDate(value: string | null): string {
	return value ? formatDate(value) : "—";
}

function formatOptionalPercent(value: number | null): string {
	return value === null ? "—" : formatPercent(value);
}

onMounted(() => void loadMarketDate());
</script>

<template>
	<section class="record-surface" aria-labelledby="market-date-detail-title">
		<RouterLink class="back-link" to="/market-dates"> ← Back to market dates </RouterLink>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading market date…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<Button label="Retry" variant="outline" @click="loadMarketDate" />
		</div>

		<template v-else-if="marketDate">
			<div class="surface-heading">
				<div>
					<p class="surface-kicker">Market date</p>
					<h2 id="market-date-detail-title">
						{{ formatDate(marketDate.date) }}
					</h2>
				</div>
				<span class="read-only-badge">Read only</span>
			</div>

			<dl class="record-detail-grid market-date-detail" data-testid="market-date-detail">
				<div>
					<dt>Date</dt>
					<dd>{{ formatDate(marketDate.date) }}</dd>
				</div>
			</dl>

			<section class="market-price-section">
				<h3>Bond Market Prices</h3>
				<div v-if="marketDate.bond_market_prices.length === 0" class="surface-state">
					This market date has no bond market prices.
				</div>
				<div v-else>
					<DataList
						:items="marketDate.bond_market_prices"
						:columns="[
							'minmax(9rem,1fr)',
							'minmax(11rem,1fr)',
							'minmax(11rem,1fr)',
							'minmax(8rem,1fr)',
							'minmax(10rem,1fr)',
							'minmax(17rem,1.5fr)',
							'minmax(11rem,1fr)',
						]"
						row-key="isin"
						data-testid="market-prices"
					>
						<template #header>
							<ListHeaderCell>ISIN</ListHeaderCell>
							<ListHeaderCell>Principal Factor</ListHeaderCell>
							<ListHeaderCell>Market Price</ListHeaderCell>
							<ListHeaderCell>Currency</ListHeaderCell>
							<ListHeaderCell>Future XIRR</ListHeaderCell>
							<ListHeaderCell>
								Weighted Average Principal Repayment Date
							</ListHeaderCell>
							<ListHeaderCell>Maturity Date</ListHeaderCell>
						</template>
						<template #row="{ item: row }">
							<ListCell data-label="ISIN">
								{{ row.isin }}
							</ListCell>
							<ListCell data-label="Principal Factor">
								{{ formatNumber(row.principal_factor, 6) }}
							</ListCell>
							<ListCell data-label="Market Price">
								{{ formatNumber(row.market_price, 6) }}
							</ListCell>
							<ListCell data-label="Currency">
								{{ row.currency }}
							</ListCell>
							<ListCell data-label="Future XIRR">
								{{ formatOptionalPercent(row.future_xirr) }}
							</ListCell>
							<ListCell data-label="Weighted Average Principal Repayment Date">
								{{ formatOptionalDate(row.weighted_avg_repayment_date) }}
							</ListCell>
							<ListCell data-label="Maturity Date">
								{{ formatDate(row.maturity_date) }}
							</ListCell>
						</template>
					</DataList>
				</div>
			</section>

			<YieldCurveChart :rows="marketDate.bond_market_prices" />
		</template>
	</section>
</template>
