<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Button, FormControl } from "frappe-ui";
import { ListCell, ListHeaderCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import SurfaceState from "../components/SurfaceState.vue";
import { useInvestorApi } from "../lib/api";
import { formatDate, formatMoney, formatNumber } from "../lib/format";
import { useReportRequest } from "../lib/report";
import type { InterestDifferenceColumn, InterestDifferenceRow } from "../report-types";
import type { InvestorBootstrap } from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const api = useInvestorApi();
const selectedPortfolio = ref("");
const fromDate = ref("");
const toDate = ref("");
const { report, loading, hasRun, error, load, invalidate } = useReportRequest(
	() =>
		api.fetchInterestDifference({
			portfolio: selectedPortfolio.value,
			fromDate: fromDate.value || undefined,
			toDate: toDate.value || undefined,
		}),
	"Interest difference could not be loaded. Please retry."
);
const dateRangeInvalid = computed(() =>
	Boolean(fromDate.value && toDate.value && fromDate.value > toDate.value)
);
const canRun = computed(() => Boolean(selectedPortfolio.value) && !loading.value);
const portfolioOptions = computed(() => [
	{ label: "Select portfolio", value: "" },
	...props.bootstrap.portfolios.map((portfolio) => ({
		label: portfolio.label,
		value: portfolio.name,
	})),
]);
watch([selectedPortfolio, fromDate, toDate], invalidate);

async function runReport(): Promise<void> {
	// DatePicker commits typed text on blur. Let those model updates settle before
	// validating, so Run stays available while a user replaces both dates.
	await nextTick();
	if (!canRun.value) {
		return;
	}
	if (dateRangeInvalid.value) {
		return;
	}

	await load();
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
		<DataList
			v-else-if="report"
			:items="report.rows"
			:columns="
				report.columns.map((column) =>
					column.label.length > 18 ? 'minmax(15rem, 1fr)' : 'minmax(9rem, 1fr)'
				)
			"
			:row-key="(row, index) => `${row.transaction_reference}:${row.currency}:${index}`"
			:row-test-id="
				(row) =>
					row.is_total_row ? 'interest-difference-total-row' : 'interest-difference-row'
			"
			:row-class="(row) => ({ 'interest-difference-total-row': row.is_total_row })"
			data-testid="interest-difference-table"
		>
			<template #header>
				<ListHeaderCell
					v-for="column in report.columns"
					:key="column.fieldname"
					:class="{ 'justify-end': isNumericColumn(column) }"
				>
					{{ column.label }}
				</ListHeaderCell>
			</template>
			<template #row="{ item: row }">
				<ListCell
					v-for="column in report.columns"
					:key="column.fieldname"
					:class="{ 'justify-end': isNumericColumn(column) }"
				>
					{{ displayValue(row, column) }}
				</ListCell>
			</template>
		</DataList>
	</section>
</template>
