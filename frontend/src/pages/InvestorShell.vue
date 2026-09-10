<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import {
	Avatar,
	Badge,
	Breadcrumbs,
	Button,
	DesktopShell,
	ErrorMessage,
	MobileNav,
	MobileNavItem,
	MobileShell,
	PageHeader,
	PageHeaderMobile,
	ScrollArea,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarLabel,
} from "frappe-ui";
import { useRoute } from "vue-router";

import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
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
const api = useInvestorApi();
const isMobile = ref(false);
const shellComponent = computed(() => (isMobile.value ? MobileShell : DesktopShell));
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
const breadcrumbItems = computed(() => {
	const items = [{ label: "Home", route: "/" }];

	if (!isHome.value) {
		items.push({ label: "Bond Investor", route: "/" });
	}
	if (isDetail.value && currentSectionItem.value) {
		items.push({
			label: currentSectionItem.value.label,
			route: currentSectionItem.value.path,
		});
	}

	return items;
});

function isNavigationItemActive(name: string): boolean {
	return activeNavigationName.value === name;
}

function updateMobileLayout(): void {
	isMobile.value = window.innerWidth < 768;
}

async function loadBootstrap(): Promise<void> {
	error.value = null;

	try {
		bootstrap.value = await api.fetchBootstrap();
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

async function focusPageHeading(): Promise<void> {
	await nextTick();
	const heading =
		pageHeading.value ?? document.querySelector<HTMLElement>('[data-slot="mobile-shell"] h1');
	heading?.focus();
}

onMounted(() => {
	updateMobileLayout();
	window.addEventListener("resize", updateMobileLayout);
	void focusPageHeading();
	void loadBootstrap();
});

onBeforeUnmount(() => window.removeEventListener("resize", updateMobileLayout));
</script>

<template>
	<component
		:is="shellComponent"
		class="investor-shell bg-surface-gray-1 text-ink-gray-8"
		data-testid="investor-shell"
	>
		<template #sidebar>
			<Sidebar
				v-if="!isMobile"
				disable-collapse
				width="14rem"
				class="investor-navigation overflow-hidden border-r border-outline-gray-1"
			>
				<SidebarHeader title="Bond Management" subtitle="Bond Investor" :menu-items="[]">
					<template #prefix>
						<div
							class="grid size-7 place-items-center rounded-1 border border-outline-blue-2 bg-surface-blue-2 text-xs-bold text-ink-blue-7"
							aria-hidden="true"
						>
							BM
						</div>
					</template>
				</SidebarHeader>

				<div class="flex min-h-0 flex-1 flex-col px-2 pb-2">
					<SidebarLabel class="px-2">Workspace</SidebarLabel>
					<ScrollArea class="min-h-0 flex-1" viewport-class="px-0.5 pb-2">
						<nav aria-label="Investor navigation" class="space-y-0.5">
							<SidebarItem
								v-for="item in INVESTOR_NAVIGATION"
								:key="item.name"
								:to="item.path"
								:label="item.label"
								:icon="item.icon"
								:active="isNavigationItemActive(item.name)"
							/>
						</nav>
					</ScrollArea>

					<div
						class="investor-navigation__footer mt-2 grid shrink-0 gap-2 border-t border-outline-gray-1 px-2 pt-3 text-p-xs text-ink-gray-5"
					>
						<Badge theme="gray" variant="outline" size="sm">View only</Badge>
						<span>Desk-compatible investor view</span>
					</div>
				</div>
			</Sidebar>
		</template>

		<template #nav>
			<MobileNav
				v-if="isMobile"
				class="investor-mobile-navigation"
				aria-label="Investor navigation"
			>
				<MobileNavItem
					v-for="item in INVESTOR_NAVIGATION"
					:key="item.name"
					:to="item.path"
					:label="item.label"
					:icon="item.icon"
					:active="isNavigationItemActive(item.name)"
				/>
			</MobileNav>
		</template>

		<PageHeader v-if="!isMobile" class="investor-page-header">
			<div class="flex w-full min-w-0 items-center justify-between gap-4">
				<nav
					aria-label="Breadcrumb"
					class="flex min-w-0 flex-1 items-center overflow-hidden"
				>
					<Breadcrumbs :items="breadcrumbItems" class="min-w-0 shrink">
						<template #prefix="{ item }">
							<span
								v-if="item.label === 'Home'"
								class="lucide-house mr-1 size-4 text-ink-gray-5"
								aria-hidden="true"
							/>
						</template>
					</Breadcrumbs>
					<span class="mx-1 text-ink-gray-4" aria-hidden="true">/</span>
					<h1
						id="investor-title"
						ref="pageHeading"
						tabindex="-1"
						class="min-w-0 truncate text-xl-semibold text-ink-gray-9"
					>
						{{ pageTitle }}
					</h1>
				</nav>

				<div v-if="bootstrap" class="flex shrink-0 items-center gap-3">
					<a
						class="flex items-center gap-1 text-sm text-ink-gray-5 hover:text-ink-gray-8"
						href="/desk/bond-investor"
					>
						<span>Open Desk</span>
						<span class="lucide-external-link size-3.5" aria-hidden="true" />
					</a>
					<div class="flex min-w-0 items-center gap-2">
						<Avatar :label="bootstrap.user.full_name" size="sm" theme="blue" />
						<div class="hidden min-w-0 flex-col md:flex">
							<strong class="truncate text-sm-medium text-ink-gray-8">
								{{ bootstrap.user.full_name }}
							</strong>
							<span class="text-xs text-ink-gray-5">Investor access</span>
						</div>
					</div>
				</div>
			</div>
		</PageHeader>

		<PageHeaderMobile v-else :title="pageTitle" class="investor-mobile-page-header">
			<template #suffix>
				<Avatar
					v-if="bootstrap"
					:label="bootstrap.user.full_name"
					size="sm"
					theme="blue"
				/>
			</template>
		</PageHeaderMobile>

		<main class="investor-card min-h-full bg-surface-gray-1">
			<nav
				v-if="isMobile"
				class="border-b border-outline-gray-1 px-3 py-2 sm:px-5"
				aria-label="Breadcrumb"
			>
				<Breadcrumbs :items="breadcrumbItems" class="min-w-0">
					<template #prefix="{ item }">
						<span
							v-if="item.label === 'Home'"
							class="lucide-house mr-1 size-4 text-ink-gray-5"
							aria-hidden="true"
						/>
					</template>
				</Breadcrumbs>
			</nav>

			<div class="investor-page-content px-3 pb-10 pt-5 sm:px-5">
				<div
					v-if="error"
					class="status-panel status-panel--error flex items-center gap-3 rounded-4 border border-outline-red-3 bg-surface-red-2 px-3 py-2 text-sm text-ink-red-7"
				>
					<ErrorMessage class="m-0" :message="error" />
					<Button
						class="ml-auto"
						label="Retry"
						theme="blue"
						variant="outline"
						@click="loadBootstrap"
					/>
				</div>

				<p
					v-if="isHome && bootstrap"
					class="compatibility-note max-w-2xl text-p-sm text-ink-gray-5"
				>
					Browse assigned portfolio records, shared bond data and investor reports from
					the navigation.
				</p>

				<TransactionList
					v-else-if="isTransactionList && bootstrap"
					:bootstrap="bootstrap"
				/>

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

				<div
					v-else-if="bootstrap"
					class="not-found-state rounded-4 border border-dashed border-outline-red-3 bg-surface-red-2 p-4 text-p-sm text-ink-red-7"
					data-testid="not-found"
				>
					<strong>This investor page does not exist.</strong>
					<p class="m-0 mt-1">
						Use the investor navigation to return to an available route.
					</p>
				</div>
			</div>
		</main>
	</component>
</template>
