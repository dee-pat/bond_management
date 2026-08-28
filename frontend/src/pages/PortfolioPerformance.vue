<script setup lang="ts">
import { computed, ref, watch } from "vue";

import {
	fetchPortfolioPerformance,
	fetchPortfolioPerformanceCashflows,
	InvestorApiError,
	redirectToLogin,
} from "../lib/api";
import type {
	PerformanceCashflow,
	PerformanceCashflowSelection,
	PortfolioPerformanceReport,
} from "../report-types";
import type { InvestorBootstrap } from "../types";
import PortfolioPerformanceTable from "./PortfolioPerformanceTable.vue";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();

const selectedPortfolio = ref("");
const valuationDate = ref(currentDate());
const report = ref<PortfolioPerformanceReport | null>(null);
const loading = ref(false);
const hasRun = ref(false);
const error = ref<string | null>(null);
const copyingKey = ref<string | null>(null);
const copyFeedback = ref<{ kind: "empty" | "error" | "success"; message: string } | null>(null);
const hasAssignments = computed(() => props.bootstrap.portfolios.length > 0);
const canRun = computed(
	() =>
		hasAssignments.value &&
		Boolean(selectedPortfolio.value) &&
		Boolean(valuationDate.value) &&
		!loading.value
);
let latestReportRequest = 0;
let latestCashflowRequest = 0;

watch([selectedPortfolio, valuationDate], invalidateResults);

async function runReport(): Promise<void> {
	if (!canRun.value) {
		return;
	}

	const requestId = ++latestReportRequest;
	++latestCashflowRequest;
	hasRun.value = true;
	loading.value = true;
	error.value = null;
	report.value = null;
	resetCopyState();

	try {
		const response = await fetchPortfolioPerformance({
			portfolio: selectedPortfolio.value,
			valuationDate: valuationDate.value,
		});
		if (requestId === latestReportRequest) {
			report.value = response.report;
		}
	} catch (caughtError) {
		if (requestId !== latestReportRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Portfolio performance could not be loaded. Please retry.";
	} finally {
		if (requestId === latestReportRequest) {
			loading.value = false;
		}
	}
}

async function copyCashflows(selection: PerformanceCashflowSelection): Promise<void> {
	if (!report.value) {
		return;
	}

	const requestId = ++latestCashflowRequest;
	const filters = report.value.filters;
	copyingKey.value = selection.key;
	copyFeedback.value = null;

	try {
		const response = await fetchPortfolioPerformanceCashflows({
			portfolio: filters.portfolio,
			valuationDate: filters.valuation_date,
			isin: selection.isin,
			xirrType: selection.xirr_type,
			cashflowCurrency: selection.cashflow_currency,
		});
		if (requestId !== latestCashflowRequest) {
			return;
		}
		if (response.cashflows.length === 0) {
			copyingKey.value = null;
			copyFeedback.value = { kind: "empty", message: "No cash flows found." };
			return;
		}

		await navigator.clipboard.writeText(cashflowsToTsv(response.cashflows));
		if (requestId === latestCashflowRequest) {
			copyFeedback.value = {
				kind: "success",
				message: `Copied ${response.cashflows.length} cash flows.`,
			};
		}
	} catch (caughtError) {
		if (requestId !== latestCashflowRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		copyFeedback.value = {
			kind: "error",
			message: "Cash flows could not be copied. Please retry.",
		};
	} finally {
		if (requestId === latestCashflowRequest) {
			copyingKey.value = null;
		}
	}
}

function invalidateResults(): void {
	++latestReportRequest;
	++latestCashflowRequest;
	report.value = null;
	loading.value = false;
	hasRun.value = false;
	error.value = null;
	resetCopyState();
}

function resetCopyState(): void {
	copyingKey.value = null;
	copyFeedback.value = null;
}

function currentDate(): string {
	const today = new Date();
	const localToday = new Date(today.getTime() - today.getTimezoneOffset() * 60_000);
	return localToday.toISOString().slice(0, 10);
}

function cashflowsToTsv(cashflows: PerformanceCashflow[]): string {
	return [
		"isin\ttransaction_type\tdate\tcurrency\tamount\tquantity\trate",
		...cashflows.map((cashflow) =>
			[
				sanitizedText(cashflow.isin),
				sanitizedText(cashflow.transaction_type),
				sanitizedText(cashflow.date),
				sanitizedText(cashflow.currency),
				String(cashflow.amount),
				String(cashflow.quantity),
				String(cashflow.rate),
			].join("\t")
		),
	].join("\n");
}

function sanitizedText(value: string): string {
	const text = String(value ?? "").replace(/\p{Cc}/gu, " ");
	return /^[=+\-@]/.test(text) ? `'${text}` : text;
}
</script>

<template>
	<section class="record-surface performance-surface" aria-label="Portfolio performance report">
		<div v-if="!hasAssignments" class="surface-state" data-testid="performance-no-assignments">
			No portfolios are assigned to your account.
		</div>

		<template v-else>
			<form
				class="performance-filters"
				data-testid="performance-filters"
				@submit.prevent="runReport"
			>
				<div class="surface-filter">
					<label for="performance-portfolio">Portfolio</label>
					<select
						id="performance-portfolio"
						v-model="selectedPortfolio"
						name="portfolio"
						required
					>
						<option value="">Select portfolio</option>
						<option
							v-for="portfolio in bootstrap.portfolios"
							:key="portfolio.name"
							:value="portfolio.name"
						>
							{{ portfolio.label }}
						</option>
					</select>
				</div>

				<div class="surface-filter">
					<label for="performance-valuation-date">Valuation Date</label>
					<input
						id="performance-valuation-date"
						v-model="valuationDate"
						name="valuation_date"
						type="date"
						required
					/>
				</div>

				<button class="performance-run-button" type="submit" :disabled="!canRun">
					Run
				</button>
			</form>

			<div v-if="loading" class="surface-state" aria-live="polite">
				Loading portfolio performance…
			</div>

			<div v-else-if="error" class="surface-state surface-state--error" role="alert">
				<p>{{ error }}</p>
				<button class="secondary-button" type="button" @click="runReport">Retry</button>
			</div>

			<div v-else-if="!hasRun" class="surface-state" data-testid="performance-initial">
				Select a portfolio, then run the report.
			</div>

			<div
				v-else-if="report && report.rows.length === 0"
				class="surface-state"
				data-testid="performance-empty"
			>
				No portfolio performance was found for these filters.
			</div>

			<template v-else-if="report">
				<PortfolioPerformanceTable
					:columns="report.columns"
					:rows="report.rows"
					:copying-key="copyingKey"
					@copy="copyCashflows"
				/>
				<p v-if="copyingKey" class="performance-copy-feedback" aria-live="polite">
					Copying cash flows…
				</p>
				<p
					v-else-if="copyFeedback"
					class="performance-copy-feedback"
					:class="`performance-copy-feedback--${copyFeedback.kind}`"
					:role="copyFeedback.kind === 'error' ? 'alert' : 'status'"
				>
					{{ copyFeedback.message }}
				</p>
			</template>
		</template>
	</section>
</template>
