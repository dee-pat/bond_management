<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button, FormControl } from "frappe-ui";

import SurfaceState from "../components/SurfaceState.vue";
import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import { formatDate, formatMoney, formatNumber } from "../lib/format";
import type {
	InterestDifferenceColumn,
	InterestDifferenceReport,
	InterestDifferenceRow,
} from "../report-types";
import type { InvestorBootstrap } from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const api = useInvestorApi();
const selectedPortfolio = ref("");
const fromDate = ref("");
const toDate = ref("");
const report = ref<InterestDifferenceReport | null>(null);
const loading = ref(false);
const hasRun = ref(false);
const error = ref<string | null>(null);
const dateRangeInvalid = computed(() =>
	Boolean(fromDate.value && toDate.value && fromDate.value > toDate.value)
);
const canRun = computed(
	() => Boolean(selectedPortfolio.value) && !dateRangeInvalid.value && !loading.value
);
const portfolioOptions = computed(() => [
	{ label: "Select portfolio", value: "" },
	...props.bootstrap.portfolios.map((portfolio) => ({
		label: portfolio.label,
		value: portfolio.name,
	})),
]);
let latestRequest = 0;

watch([selectedPortfolio, fromDate, toDate], invalidateResults);

async function runReport(): Promise<void> {
	if (!canRun.value) {
		return;
	}

	const requestId = ++latestRequest;
	hasRun.value = true;
	loading.value = true;
	error.value = null;
	report.value = null;

	try {
		const response = await api.fetchInterestDifference({
			portfolio: selectedPortfolio.value,
			fromDate: fromDate.value || undefined,
			toDate: toDate.value || undefined,
		});
		if (requestId === latestRequest) {
			report.value = response.report;
		}
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Interest difference could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

function invalidateResults(): void {
	++latestRequest;
	report.value = null;
	loading.value = false;
	hasRun.value = false;
	error.value = null;
}

function displayValue(row: InterestDifferenceRow, column: InterestDifferenceColumn): string {
	const value = row[column.fieldname];
	if (value === null || value === undefined || value === "") {
		return "";
	}
	if (column.fieldtype === "Date" && typeof value === "string") {
		return formatDate(value);
	}
	if (typeof value !== "number") {
		return value;
	}
	if (column.fieldtype === "Currency") {
		const currency = typeof row.currency === "string" ? row.currency : "";
		return formatMoney(value, currency, column.precision ?? 2);
	}
	if (column.fieldtype === "Float") {
		return formatNumber(value, column.precision ?? 2);
	}
	return String(value);
}

function isNumericColumn(column: InterestDifferenceColumn): boolean {
	return column.fieldtype === "Currency" || column.fieldtype === "Float";
}
</script>

<template>
	<section
		class="record-surface interest-difference-surface"
		aria-label="Interest difference report"
	>
		<form
			class="interest-difference-filters"
			data-testid="interest-difference-filters"
			@submit.prevent="runReport"
		>
			<FormControl
				id="interest-difference-portfolio"
				v-model="selectedPortfolio"
				class="surface-filter"
				label="Portfolio"
				type="select"
				:options="portfolioOptions"
				required
			/>
			<FormControl
				id="interest-difference-from-date"
				v-model="fromDate"
				class="surface-filter"
				label="From Settlement Date"
				type="date"
			/>
			<FormControl
				id="interest-difference-to-date"
				v-model="toDate"
				class="surface-filter"
				label="To Settlement Date"
				type="date"
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

		<p v-if="dateRangeInvalid" class="interest-difference-error" role="alert">
			From Settlement Date must be on or before To Settlement Date.
		</p>
		<SurfaceState
			v-if="loading"
			:loading="loading"
			loading-text="Loading interest difference…"
		/>
		<SurfaceState v-else-if="error" :error="error" @retry="runReport" />
		<div v-else-if="!hasRun" class="surface-state" data-testid="interest-difference-initial">
			Select a portfolio, then run the report.
		</div>
		<div
			v-else-if="report && report.rows.length === 0"
			class="surface-state"
			data-testid="interest-difference-empty"
		>
			No interest differences were found for these filters.
		</div>
		<div v-else-if="report" class="interest-difference-table-wrap">
			<table class="interest-difference-table" data-testid="interest-difference-table">
				<thead>
					<tr>
						<th
							v-for="column in report.columns"
							:key="column.fieldname"
							:class="{ 'interest-difference-numeric': isNumericColumn(column) }"
							scope="col"
						>
							{{ column.label }}
						</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="(row, index) in report.rows"
						:key="`${row.transaction_reference}:${row.currency}:${index}`"
						:data-testid="
							row.transaction_reference === 'Total'
								? 'interest-difference-total-row'
								: 'interest-difference-row'
						"
						:class="{
							'interest-difference-total-row': row.transaction_reference === 'Total',
						}"
					>
						<td
							v-for="column in report.columns"
							:key="column.fieldname"
							:class="{ 'interest-difference-numeric': isNumericColumn(column) }"
						>
							{{ displayValue(row, column) }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</section>
</template>
