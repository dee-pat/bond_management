<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Avatar, Badge, Button, Icon } from "frappe-ui";
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

const DETAIL_PARENT_BY_ROUTE: Record<string, string> = {
	"transaction-detail": "transactions",
	"statement-detail": "statements",
	"bond-detail": "bonds",
	"market-date-detail": "market-dates",
	"exchange-rate-detail": "exchange-rates",
};

const route = useRoute();
const pageHeading = ref<HTMLHeadingElement | null>(null);
const bootstrap = ref<InvestorBootstrap | null>(null);
const error = ref<string | null>(null);
const mobileNavigationOpen = ref(false);
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
const isDetail = computed(() => typeof route.name === "string" && route.name.endsWith("-detail"));
const activeNavigationName = computed(() => {
	if (typeof route.name === "string" && DETAIL_PARENT_BY_ROUTE[route.name]) {
		return DETAIL_PARENT_BY_ROUTE[route.name];
	}
	return currentItem.value?.name;
});
const currentSectionItem = computed(() =>
	INVESTOR_NAVIGATION.find((item) => item.name === activeNavigationName.value)
);
const pageTitle = computed(() => {
	if (isHome.value) {
		return "Bond Investor";
	}
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
const currentSectionLabel = computed(() => currentSectionItem.value?.label);

function isNavigationItemActive(name: string): boolean {
	return activeNavigationName.value === name;
}

function closeMobileNavigation(): void {
	mobileNavigationOpen.value = false;
}

async function loadBootstrap(): Promise<void> {
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
	}
}

onMounted(() => {
	pageHeading.value?.focus();
	void loadBootstrap();
});
</script>

<template>
	<div class="investor-shell" data-testid="investor-shell">
		<header class="investor-navbar">
			<div class="investor-navbar__left">
				<Button
					class="investor-mobile-menu-button"
					:aria-expanded="mobileNavigationOpen"
					aria-label="Toggle investor navigation"
					icon="menu"
					variant="ghost"
					@click="mobileNavigationOpen = !mobileNavigationOpen"
				/>
				<RouterLink
					class="investor-navbar__brand"
					to="/"
					aria-label="Bond Management home"
				>
					<span class="investor-brand__mark" aria-hidden="true">BM</span>
					<span class="investor-navbar__brand-name">Bond Management</span>
				</RouterLink>
				<span class="investor-navbar__divider" aria-hidden="true" />
				<span class="investor-navbar__context">Bond Investor</span>
			</div>

			<div class="investor-navbar__search" aria-label="Search">
				<Icon name="search" aria-hidden="true" />
				<span>Search or jump to…</span>
				<kbd>⌘ K</kbd>
			</div>

			<div class="investor-navbar__right">
				<a class="investor-navbar__desk-link" href="/desk/bond-investor">
					Open Desk
					<Icon name="external-link" aria-hidden="true" />
				</a>
				<div v-if="bootstrap" class="investor-account">
					<Avatar :label="bootstrap.user.full_name" size="sm" theme="blue" />
					<div class="investor-account__copy">
						<strong>{{ bootstrap.user.full_name }}</strong>
						<span>Investor access</span>
					</div>
				</div>
			</div>
		</header>

		<div class="investor-layout">
			<aside
				class="investor-navigation"
				:class="{ 'investor-navigation--open': mobileNavigationOpen }"
			>
				<div class="investor-navigation__heading">
					<span>Workspace</span>
					<strong>Bond Investor</strong>
				</div>

				<nav aria-label="Investor navigation">
					<RouterLink
						v-for="item in INVESTOR_NAVIGATION"
						:key="item.name"
						:to="item.path"
						:aria-current="isNavigationItemActive(item.name) ? 'page' : undefined"
						:class="[
							'investor-navigation__link',
							{
								'investor-navigation__link--active': isNavigationItemActive(
									item.name
								),
							},
						]"
						@click="closeMobileNavigation"
					>
						<Icon
							:name="item.icon"
							class="investor-navigation__icon"
							aria-hidden="true"
						/>
						<span>{{ item.label }}</span>
					</RouterLink>
				</nav>

				<div class="investor-navigation__footer">
					<Badge theme="gray" variant="outline" size="sm">View only</Badge>
					<span>Desk-compatible investor view</span>
				</div>
			</aside>

			<main class="investor-card">
				<header class="investor-page-header">
					<nav class="investor-breadcrumbs" aria-label="Breadcrumb">
						<RouterLink
							class="investor-breadcrumbs__home"
							to="/"
							aria-label="Home"
							title="Home"
						>
							<Icon name="home" aria-hidden="true" />
						</RouterLink>
						<span class="investor-breadcrumbs__separator" aria-hidden="true">/</span>
						<template v-if="isHome">
							<h1
								id="investor-title"
								ref="pageHeading"
								tabindex="-1"
								class="investor-breadcrumbs__current"
								aria-current="page"
							>
								{{ pageTitle }}
							</h1>
						</template>
						<template v-else>
							<RouterLink to="/">Bond Investor</RouterLink>
							<span class="investor-breadcrumbs__separator" aria-hidden="true"
								>/</span
							>
							<template v-if="isDetail">
								<RouterLink :to="currentSectionItem?.path ?? '/'">
									{{ currentSectionLabel ?? "Bond Investor" }}
								</RouterLink>
								<span class="investor-breadcrumbs__separator" aria-hidden="true"
									>/</span
								>
							</template>
							<h1
								id="investor-title"
								ref="pageHeading"
								tabindex="-1"
								class="investor-breadcrumbs__current"
								aria-current="page"
							>
								{{ pageTitle }}
							</h1>
						</template>
					</nav>
				</header>

				<div v-if="error" class="status-panel status-panel--error" role="alert">
					<p>{{ error }}</p>
					<Button label="Retry" theme="blue" variant="outline" @click="loadBootstrap" />
				</div>

				<div class="investor-page-content">
					<p v-if="isHome && bootstrap" class="compatibility-note">
						Browse assigned portfolio records, shared bond data and investor reports
						from the navigation.
					</p>

					<TransactionList
						v-else-if="isTransactionList && bootstrap"
						:bootstrap="bootstrap"
					/>

					<TransactionDetail v-else-if="isTransactionDetail && bootstrap" />

					<StatementList
						v-else-if="isStatementList && bootstrap"
						:bootstrap="bootstrap"
					/>

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
				</div>
			</main>
		</div>
	</div>
</template>
