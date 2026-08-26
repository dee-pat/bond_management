<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button } from "frappe-ui";
import { RouterLink, useRoute } from "vue-router";

import { fetchBootstrap, InvestorApiError, redirectToLogin } from "../lib/api";
import { INVESTOR_NAVIGATION } from "../navigation";
import type { InvestorBootstrap } from "../types";
import BondDetail from "./BondDetail.vue";
import BondList from "./BondList.vue";
import ExchangeRateDetail from "./ExchangeRateDetail.vue";
import ExchangeRateList from "./ExchangeRateList.vue";
import MarketDateDetail from "./MarketDateDetail.vue";
import MarketDateList from "./MarketDateList.vue";
import PortfolioPerformance from "./PortfolioPerformance.vue";
import StatementDetail from "./StatementDetail.vue";
import StatementList from "./StatementList.vue";
import TransactionDetail from "./TransactionDetail.vue";
import TransactionList from "./TransactionList.vue";
import YieldComparison from "./YieldComparison.vue";

const route = useRoute();
const pageHeading = ref<HTMLHeadingElement | null>(null);
const bootstrap = ref<InvestorBootstrap | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const currentItem = computed(() => INVESTOR_NAVIGATION.find((item) => item.name === route.name));
const isHome = computed(() => currentItem.value?.name === "home");
const isTransactionList = computed(() => route.name === "transactions");
const isTransactionDetail = computed(() => route.name === "transaction-detail");
const isStatementList = computed(() => route.name === "statements");
const isStatementDetail = computed(() => route.name === "statement-detail");
const isBondList = computed(() => route.name === "bonds");
const isBondDetail = computed(() => route.name === "bond-detail");
const isMarketDateList = computed(() => route.name === "market-dates");
const isMarketDateDetail = computed(() => route.name === "market-date-detail");
const isExchangeRateList = computed(() => route.name === "exchange-rates");
const isExchangeRateDetail = computed(() => route.name === "exchange-rate-detail");
const isPortfolioPerformance = computed(() => route.name === "performance");
const isYieldComparison = computed(() => route.name === "yield-comparison");
const pageTitle = computed(() => {
	if (isTransactionDetail.value) {
		return "Bond Transaction";
	}
	if (isStatementDetail.value) {
		return "Bond Statement";
	}
	if (isBondDetail.value) {
		return "Bond Master";
	}
	if (isMarketDateDetail.value) {
		return "Bond Market Date";
	}
	if (isExchangeRateDetail.value) {
		return "Bond Exchange Rate";
	}
	return currentItem.value?.label ?? "Page not found";
});

async function loadBootstrap(): Promise<void> {
	loading.value = true;
	error.value = null;

	try {
		bootstrap.value = await fetchBootstrap();
	} catch (caughtError) {
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}

		error.value =
			caughtError instanceof InvestorApiError && caughtError.status === 403
				? "Your account is not permitted to access this application."
				: "The investor application could not load. Please retry.";
	} finally {
		loading.value = false;
	}
}

onMounted(() => {
	pageHeading.value?.focus();
	void loadBootstrap();
});
</script>

<template>
	<main class="investor-shell" data-testid="investor-shell">
		<aside class="investor-navigation">
			<div class="investor-brand">
				<span class="investor-brand__mark" aria-hidden="true">BM</span>
				<div>
					<strong>Bond Management</strong>
					<span>Investor portal</span>
				</div>
			</div>

			<nav aria-label="Investor navigation">
				<RouterLink
					v-for="item in INVESTOR_NAVIGATION"
					:key="item.name"
					:to="item.path"
					class="investor-navigation__link"
				>
					{{ item.label }}
				</RouterLink>
			</nav>
		</aside>

		<section class="investor-card" aria-labelledby="investor-title">
			<p class="eyebrow">Bond Management</p>
			<h1 id="investor-title" ref="pageHeading" tabindex="-1">
				{{ isHome ? "Bond Investor" : pageTitle }}
			</h1>
			<p class="subtitle">
				{{ isHome ? "Read-only investor application" : "Read-only investor surface" }}
			</p>

			<div v-if="loading" class="status-panel" aria-live="polite">
				<span class="status-dot status-dot--loading" aria-hidden="true" />
				<span>Connecting to your investor session…</span>
			</div>

			<div v-else-if="error" class="status-panel status-panel--error" role="alert">
				<p>{{ error }}</p>
				<Button label="Retry" theme="blue" variant="outline" @click="loadBootstrap" />
			</div>

			<div
				v-else
				class="status-panel status-panel--success"
				data-testid="bootstrap-status"
				aria-live="polite"
			>
				<span class="status-dot" aria-hidden="true" />
				<div>
					<strong>Connected as {{ bootstrap?.user.full_name }}</strong>
					<p>{{ bootstrap?.portfolios.length ?? 0 }} assigned portfolios available.</p>
				</div>
			</div>

			<p v-if="isHome && bootstrap" class="compatibility-note">
				Browse assigned portfolio records, shared bond data and investor reports from the
				navigation.
			</p>

			<TransactionList v-else-if="isTransactionList && bootstrap" :bootstrap="bootstrap" />

			<TransactionDetail v-else-if="isTransactionDetail && bootstrap" />

			<StatementList v-else-if="isStatementList && bootstrap" :bootstrap="bootstrap" />

			<StatementDetail v-else-if="isStatementDetail && bootstrap" />

			<BondList v-else-if="isBondList && bootstrap" />

			<BondDetail v-else-if="isBondDetail && bootstrap" />

			<MarketDateList v-else-if="isMarketDateList && bootstrap" />

			<MarketDateDetail v-else-if="isMarketDateDetail && bootstrap" />

			<ExchangeRateList v-else-if="isExchangeRateList && bootstrap" />

			<ExchangeRateDetail v-else-if="isExchangeRateDetail && bootstrap" />

			<PortfolioPerformance
				v-else-if="isPortfolioPerformance && bootstrap"
				:bootstrap="bootstrap"
			/>

			<YieldComparison v-else-if="isYieldComparison && bootstrap" />

			<div v-else-if="bootstrap" class="not-found-state" data-testid="not-found">
				<strong>This investor page does not exist.</strong>
				<p>Use the investor navigation to return to an available route.</p>
			</div>
		</section>
	</main>
</template>
