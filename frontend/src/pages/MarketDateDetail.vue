<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";
import { ListCell, ListHeaderCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import SurfaceState from "../components/SurfaceState.vue";
import { useInvestorApi } from "../lib/api";
import { useRecordDetail } from "../lib/detail";
import { formatDate, formatNumber, formatPercent } from "../lib/format";
import YieldCurveChart from "./YieldCurveChart.vue";

const route = useRoute();
const api = useInvestorApi();
const {
	record: marketDate,
	loading,
	error,
	load: loadMarketDate,
} = useRecordDetail(
	async () => (await api.fetchMarketDate(String(route.params.marketDateName ?? ""))).market_date,
	{
		forbidden: "This market date is unavailable or you do not have permission to view it.",
		failed: "The market date could not be loaded. Please retry.",
	}
);

function formatOptionalDate(value: string | null): string {
	return value ? formatDate(value) : "—";
}

function formatOptionalPercent(value: number | null): string {
	return value === null ? "—" : formatPercent(value);
}
</script>

<template>
	<section class="record-surface" aria-labelledby="market-date-detail-title">
		<RouterLink class="back-link" to="/market-dates"> ← Back to market dates </RouterLink>

		<SurfaceState v-if="loading" :loading="loading" loading-text="Loading market date…" />

		<SurfaceState v-else-if="error" :error="error" @retry="loadMarketDate" />

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
