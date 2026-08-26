<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import {
	fetchBondYieldComparison,
	fetchYieldComparisonDefaults,
	InvestorApiError,
	redirectToLogin,
} from "../lib/api";
import type { BondYieldComparisonReport, YieldComparisonFieldname } from "../report-types";
import BondYieldComparisonChart from "./BondYieldComparisonChart.vue";
import YieldComparisonControls from "./YieldComparisonControls.vue";

const fromDate = ref("");
const toDate = ref("");
const report = ref<BondYieldComparisonReport | null>(null);
const selectedIsins = ref<Set<string>>(new Set());
const defaultsLoading = ref(true);
const defaultsError = ref(false);
const datesEdited = ref(false);
const loading = ref(false);
const hasRun = ref(false);
const error = ref<string | null>(null);
const copying = ref(false);
const copyFeedback = ref<{ kind: "error" | "success"; message: string } | null>(null);
const dateRangeInvalid = computed(() =>
	Boolean(fromDate.value && toDate.value && fromDate.value > toDate.value)
);
const canRun = computed(() => !defaultsLoading.value && !loading.value && !dateRangeInvalid.value);
const bonds = computed(() => {
	const currencies = new Map<string, string>();
	report.value?.rows.forEach((row) => {
		if (!currencies.has(row.isin)) {
			currencies.set(row.isin, row.currency);
		}
	});
	return [...currencies.entries()]
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([isin, currency]) => ({ isin, currency }));
});
const hasSelectedValues = computed(() =>
	(report.value?.rows ?? []).some(
		(row) => selectedIsins.value.has(row.isin) && numericValue(row.future_xirr) !== null
	)
);
const marketPricePrecision = computed(() => columnPrecision("market_price", 3));
const futureXirrPrecision = computed(() => columnPrecision("future_xirr", 3));
let latestReportRequest = 0;
let latestCopyRequest = 0;

watch([fromDate, toDate], invalidateResults);
onMounted(loadDefaultDates);

async function loadDefaultDates(): Promise<void> {
	defaultsLoading.value = true;
	defaultsError.value = false;

	try {
		const response = await fetchYieldComparisonDefaults();
		if (!datesEdited.value) {
			fromDate.value = response.filters.from_date ?? "";
			toDate.value = response.filters.to_date;
		}
	} catch (caughtError) {
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		defaultsError.value = true;
	} finally {
		defaultsLoading.value = false;
	}
}

async function runReport(): Promise<void> {
	if (!canRun.value) {
		return;
	}

	const requestId = ++latestReportRequest;
	++latestCopyRequest;
	hasRun.value = true;
	loading.value = true;
	error.value = null;
	report.value = null;
	selectedIsins.value = new Set();
	resetCopyState();

	try {
		const response = await fetchBondYieldComparison({
			fromDate: fromDate.value || undefined,
			toDate: toDate.value || undefined,
		});
		if (requestId === latestReportRequest) {
			report.value = response.report;
			selectedIsins.value = new Set(response.report.rows.map((row) => row.isin));
		}
	} catch (caughtError) {
		if (requestId !== latestReportRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Bond yield comparison could not be loaded. Please retry.";
	} finally {
		if (requestId === latestReportRequest) {
			loading.value = false;
		}
	}
}

function toggleAll(checked: boolean): void {
	selectedIsins.value = checked ? new Set(bonds.value.map((bond) => bond.isin)) : new Set();
}

function toggleBond(isin: string, checked: boolean): void {
	const next = new Set(selectedIsins.value);
	if (checked) {
		next.add(isin);
	} else {
		next.delete(isin);
	}
	selectedIsins.value = next;
}

async function copyAuditData(): Promise<void> {
	if (!report.value || copying.value) {
		return;
	}

	const requestId = ++latestCopyRequest;
	copying.value = true;
	copyFeedback.value = null;
	try {
		await navigator.clipboard.writeText(auditTsv(report.value));
		if (requestId === latestCopyRequest) {
			copyFeedback.value = {
				kind: "success",
				message: `Copied ${report.value.rows.length} audit rows.`,
			};
		}
	} catch {
		if (requestId === latestCopyRequest) {
			copyFeedback.value = {
				kind: "error",
				message: "Audit data could not be copied. Please retry.",
			};
		}
	} finally {
		if (requestId === latestCopyRequest) {
			copying.value = false;
		}
	}
}

function invalidateResults(): void {
	++latestReportRequest;
	++latestCopyRequest;
	report.value = null;
	selectedIsins.value = new Set();
	loading.value = false;
	hasRun.value = false;
	error.value = null;
	resetCopyState();
}

function resetCopyState(): void {
	copying.value = false;
	copyFeedback.value = null;
}

function columnPrecision(fieldname: YieldComparisonFieldname, fallback: number): number {
	return (
		report.value?.columns.find((column) => column.fieldname === fieldname)?.precision ??
		fallback
	);
}

function auditTsv(currentReport: BondYieldComparisonReport): string {
	const header = currentReport.columns.map((column) => auditCell(column.label)).join("\t");
	const rows = currentReport.rows.map((row) =>
		currentReport.columns.map((column) => auditCell(row[column.fieldname])).join("\t")
	);
	return [header, ...rows].join("\n");
}

function auditCell(value: unknown): string {
	const text = String(value ?? "").replace(/\p{Cc}/gu, " ");
	return /^[=+\-@]/.test(text) ? `'${text}` : text;
}

function numericValue(value: unknown): number | null {
	if (value === null || value === undefined || value === "") {
		return null;
	}
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}
</script>

<template>
	<section
		class="record-surface yield-comparison-surface"
		aria-labelledby="yield-comparison-title"
	>
		<div class="surface-heading">
			<div>
				<p class="surface-kicker">Persisted market history</p>
				<h2 id="yield-comparison-title">Yield comparison</h2>
			</div>
			<span class="read-only-badge">Read only</span>
		</div>

		<form class="yield-comparison-filters" @submit.prevent="runReport">
			<div class="surface-filter">
				<label for="yield-comparison-from-date">From Date</label>
				<input
					id="yield-comparison-from-date"
					v-model="fromDate"
					:disabled="defaultsLoading"
					name="from_date"
					type="date"
					@input="datesEdited = true"
				>
			</div>

			<div class="surface-filter">
				<label for="yield-comparison-to-date">To Date</label>
				<input
					id="yield-comparison-to-date"
					v-model="toDate"
					:disabled="defaultsLoading"
					name="to_date"
					type="date"
					@input="datesEdited = true"
				>
			</div>

			<button class="performance-run-button" type="submit" :disabled="!canRun">Run</button>
		</form>

		<p v-if="dateRangeInvalid" class="yield-comparison-date-error" role="alert">
			From Date must be on or before To Date.
		</p>

		<div v-if="defaultsLoading" class="surface-state" aria-live="polite">
			Loading default date range…
		</div>

		<div v-else-if="defaultsError" class="surface-state surface-state--error" role="alert">
			<p>Default date range could not be loaded. Please retry.</p>
			<button class="secondary-button" type="button" @click="loadDefaultDates">Retry</button>
		</div>

		<div v-else-if="loading" class="surface-state" aria-live="polite">
			Loading bond yield comparison…
		</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button class="secondary-button" type="button" @click="runReport">Retry</button>
		</div>

		<div v-else-if="!hasRun" class="surface-state" data-testid="yield-comparison-initial">
			Choose optional date bounds, then run the report.
		</div>

		<div
			v-else-if="report && report.rows.length === 0"
			class="surface-state"
			data-testid="yield-comparison-empty"
		>
			No persisted bond yields were found for these filters.
		</div>

		<template v-else-if="report">
			<YieldComparisonControls
				:bonds="bonds"
				:copy-feedback="copyFeedback"
				:copying="copying"
				:selected-isins="[...selectedIsins]"
				@copy="copyAuditData"
				@toggle-all="toggleAll"
				@toggle-bond="toggleBond"
			/>

			<div
				v-if="selectedIsins.size === 0"
				class="surface-state"
				data-testid="yield-comparison-no-selection"
			>
				Select one or more bonds to display their stored Future XIRR.
			</div>
			<div
				v-else-if="!hasSelectedValues"
				class="surface-state"
				data-testid="yield-comparison-no-values"
			>
				Selected bonds have no persisted Future XIRR values.
			</div>
			<BondYieldComparisonChart
				v-else
				:future-xirr-precision="futureXirrPrecision"
				:market-price-precision="marketPricePrecision"
				:rows="report.rows"
				:selected-isins="[...selectedIsins]"
			/>
		</template>
	</section>
</template>
