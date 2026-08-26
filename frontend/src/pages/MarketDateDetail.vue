<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { fetchMarketDate, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate, formatNumber, formatPercent } from "../lib/format";
import type { MarketDateDetail } from "../types";
import YieldCurveChart from "./YieldCurveChart.vue";

const route = useRoute();
const marketDate = ref<MarketDateDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const marketDateName = computed(() => String(route.params.marketDateName ?? ""));
let latestRequest = 0;

async function loadMarketDate(): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchMarketDate(marketDateName.value);
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
  <section
    class="record-surface"
    aria-labelledby="market-date-detail-title"
  >
    <RouterLink
      class="back-link"
      to="/market-dates"
    >
      ← Back to market dates
    </RouterLink>

    <div
      v-if="loading"
      class="surface-state"
      aria-live="polite"
    >
      Loading market date…
    </div>

    <div
      v-else-if="error"
      class="surface-state surface-state--error"
      role="alert"
    >
      <p>{{ error }}</p>
      <button
        class="secondary-button"
        type="button"
        @click="loadMarketDate"
      >
        Retry
      </button>
    </div>

    <template v-else-if="marketDate">
      <div class="surface-heading">
        <div>
          <p class="surface-kicker">
            Market date
          </p>
          <h2 id="market-date-detail-title">
            {{ formatDate(marketDate.date) }}
          </h2>
        </div>
        <span class="read-only-badge">Read only</span>
      </div>

      <dl
        class="record-detail-grid market-date-detail"
        data-testid="market-date-detail"
      >
        <div>
          <dt>Date</dt>
          <dd>{{ formatDate(marketDate.date) }}</dd>
        </div>
      </dl>

      <section class="market-price-section">
        <h3>Bond Market Prices</h3>
        <div
          v-if="marketDate.bond_market_prices.length === 0"
          class="surface-state"
        >
          This market date has no bond market prices.
        </div>
        <div
          v-else
          class="record-table-wrap"
        >
          <table
            class="record-table"
            data-testid="market-prices"
          >
            <thead>
              <tr>
                <th scope="col">
                  ISIN
                </th>
                <th scope="col">
                  Principal Factor
                </th>
                <th scope="col">
                  Market Price
                </th>
                <th scope="col">
                  Currency
                </th>
                <th scope="col">
                  Future XIRR
                </th>
                <th scope="col">
                  Weighted Average Principal Repayment Date
                </th>
                <th scope="col">
                  Maturity Date
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in marketDate.bond_market_prices"
                :key="row.isin"
              >
                <td data-label="ISIN">
                  {{ row.isin }}
                </td>
                <td data-label="Principal Factor">
                  {{ formatNumber(row.principal_factor, 6) }}
                </td>
                <td data-label="Market Price">
                  {{ formatNumber(row.market_price, 6) }}
                </td>
                <td data-label="Currency">
                  {{ row.currency }}
                </td>
                <td data-label="Future XIRR">
                  {{ formatOptionalPercent(row.future_xirr) }}
                </td>
                <td data-label="Weighted Average Principal Repayment Date">
                  {{ formatOptionalDate(row.weighted_avg_repayment_date) }}
                </td>
                <td data-label="Maturity Date">
                  {{ formatDate(row.maturity_date) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <YieldCurveChart :rows="marketDate.bond_market_prices" />
    </template>
  </section>
</template>
