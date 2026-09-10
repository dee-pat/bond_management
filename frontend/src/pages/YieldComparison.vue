<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { Button, ErrorMessage, FormControl } from "frappe-ui";

import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import SurfaceState from "../components/SurfaceState.vue";
import type { BondYieldComparisonReport, YieldComparisonFieldname } from "../report-types";
import BondYieldComparisonChart from "./BondYieldComparisonChart.vue";
import YieldComparisonControls from "./YieldComparisonControls.vue";

const fromDate = ref("");
const toDate = ref("");
const report = ref<BondYieldComparisonReport | null>(null);
const defaultsLoading = ref(true);
const defaultsError = ref(false);
const datesEdited = ref(false);
const loading = ref(false);
const hasRun = ref(false);
const error = ref<string | null>(null);
const copying = ref(false);
const copyFeedback = ref<{ kind: "error" | "success"; message: string } | null>(null);
const api = useInvestorApi();
const dateRangeInvalid = computed(() =>
	Boolean(fromDate.value && toDate.value && fromDate.value > toDate.value)
);
const canRun = computed(() => !defaultsLoading.value);
const hasPersistedValues = computed(() =>
	(report.value?.rows ?? []).some((row) => numericValue(row.future_xirr) !== null)
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
		const response = await api.fetchYieldComparisonDefaults();
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
	// DatePicker commits typed text on blur. Waiting for that update prevents a
	// disabled-state deadlock when a user replaces an initially valid date
	// range by typing into both fields before pressing Run.
	await nextTick();
	if (!canRun.value) {
		return;
	}
	if (dateRangeInvalid.value) {
		return;
	}

	const requestId = ++latestReportRequest;
	++latestCopyRequest;
	hasRun.value = true;
	loading.value = true;
	error.value = null;
	report.value = null;
	resetCopyState();

	try {
		const response = await api.fetchBondYieldComparison({
			fromDate: fromDate.value || undefined,
			toDate: toDate.value || undefined,
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
		error.value = "Bond yield comparison could not be loaded. Please retry.";
	} finally {
		if (requestId === latestReportRequest) {
			loading.value = false;
		}
	}
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
		aria-label="Bond yield comparison report"
	>
		<form class="yield-comparison-filters" @submit.prevent="runReport">
			<FormControl
				id="yield-comparison-from-date"
				v-model="fromDate"
				class="surface-filter"
				label="From Date"
				type="date"
				:disabled="defaultsLoading"
				@update:model-value="datesEdited = true"
			/>

			<FormControl
				id="yield-comparison-to-date"
				v-model="toDate"
				class="surface-filter"
				label="To Date"
				type="date"
				:disabled="defaultsLoading"
				@update:model-value="datesEdited = true"
			/>

			<Button
				class="performance-run-button"
				label="Run"
				theme="blue"
				variant="solid"
				type="submit"
				:disabled="!canRun"
			/>
		</form>

		<ErrorMessage
			v-if="dateRangeInvalid"
			class="yield-comparison-date-error"
			message="From Date must be on or before To Date."
		/>

		<SurfaceState
			v-if="defaultsLoading"
			:loading="defaultsLoading"
			loading-text="Loading default date range…"
		/>

		<SurfaceState
			v-else-if="defaultsError"
			error="Default date range could not be loaded. Please retry."
			@retry="loadDefaultDates"
		/>

		<SurfaceState
			v-else-if="loading"
			:loading="loading"
			loading-text="Loading bond yield comparison…"
		/>

		<SurfaceState v-else-if="error" :error="error" @retry="runReport" />

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
				:copy-feedback="copyFeedback"
				:copying="copying"
				@copy="copyAuditData"
			/>

			<div
				v-if="!hasPersistedValues"
				class="surface-state"
				data-testid="yield-comparison-no-values"
			>
				No persisted Future XIRR values were returned for these filters.
			</div>
			<BondYieldComparisonChart
				v-else
				:future-xirr-precision="futureXirrPrecision"
				:market-price-precision="marketPricePrecision"
				:rows="report.rows"
			/>
		</template>
	</section>
</template>
