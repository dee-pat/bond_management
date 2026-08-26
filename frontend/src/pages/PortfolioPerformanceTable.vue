<script setup lang="ts">
import { RouterLink } from "vue-router";

import type {
	PerformanceCashflowSelection,
	PerformanceColumn,
	PerformanceRow,
} from "../report-types";

const props = defineProps<{
	columns: PerformanceColumn[];
	rows: PerformanceRow[];
	copyingKey: string | null;
}>();

const emit = defineEmits<{
	copy: [selection: PerformanceCashflowSelection];
}>();

function valueFor(row: PerformanceRow, column: PerformanceColumn): string | number | null {
	return row[column.fieldname];
}

function formattedValue(row: PerformanceRow, column: PerformanceColumn): string {
	const value = valueFor(row, column);
	if (value === null || value === undefined) {
		return "";
	}
	if (typeof value !== "number") {
		return value;
	}

	const precision = column.precision ?? 0;
	if (column.fieldtype === "Currency") {
		return formatCurrency(value, currencyFor(row, column), precision);
	}
	if (column.fieldtype === "Percent") {
		return `${formatNumber(value, displayedPercentPrecision(value, precision))}%`;
	}
	if (column.fieldtype === "Float") {
		return formatNumber(value, precision);
	}
	return String(value);
}

function currencyFor(row: PerformanceRow, column: PerformanceColumn): string {
	if (!column.options) {
		return "";
	}
	const value = row[column.options as keyof PerformanceRow];
	return typeof value === "string" ? value : "";
}

function formatCurrency(value: number, currency: string, precision: number): string {
	if (!currency) {
		return formatNumber(value, precision);
	}

	try {
		return new Intl.NumberFormat("en-GB", {
			style: "currency",
			currency,
			currencyDisplay: "code",
			minimumFractionDigits: precision,
			maximumFractionDigits: precision,
		}).format(value);
	} catch {
		return `${currency} ${formatNumber(value, precision)}`;
	}
}

function formatNumber(value: number, precision: number): string {
	return new Intl.NumberFormat("en-GB", {
		minimumFractionDigits: precision,
		maximumFractionDigits: precision,
	}).format(value);
}

function displayedPercentPrecision(value: number, precision: number): number {
	const fraction = Math.abs(value).toFixed(precision).split(".")[1] ?? "";
	return fraction.replace(/0+$/, "").length;
}

function actionFor(
	row: PerformanceRow,
	column: PerformanceColumn
): PerformanceCashflowSelection | null {
	const action = column.cashflow_action;
	if (
		!action ||
		valueFor(row, column) === null ||
		(row.isin === "TOTAL" && action.cashflow_currency === "native" && !row.currency)
	) {
		return null;
	}

	return {
		isin: row.isin,
		...action,
		key: `${row.isin}:${column.fieldname}:${action.cashflow_currency}`,
	};
}
</script>

<template>
  <div class="performance-table-wrap">
    <table
      class="performance-table"
      data-testid="performance-table"
    >
      <thead>
        <tr>
          <th
            v-for="column in props.columns"
            :key="column.fieldname"
            scope="col"
            :title="column.description ?? undefined"
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in props.rows"
          :key="row.isin"
          :class="{ 'performance-table__total': row.isin === 'TOTAL' }"
          data-testid="performance-row"
        >
          <td
            v-for="column in props.columns"
            :key="column.fieldname"
            :data-label="column.label"
          >
            <RouterLink
              v-if="column.fieldname === 'isin' && row.isin !== 'TOTAL'"
              :to="`/bonds/${encodeURIComponent(row.isin)}`"
              :aria-label="`View bond ${row.isin}`"
            >
              {{ row.isin }}
            </RouterLink>
            <strong v-else-if="column.fieldname === 'isin' && row.isin === 'TOTAL'">
              TOTAL
            </strong>
            <button
              v-else-if="actionFor(row, column)"
              class="performance-cashflow-button"
              type="button"
              :disabled="copyingKey !== null"
              :aria-label="`Copy ${
                actionFor(row, column)?.cashflow_currency
              } cash flows for ${row.isin} ${column.label}`"
              @click="emit('copy', actionFor(row, column)!)"
            >
              {{ formattedValue(row, column) }}
            </button>
            <span v-else>{{ formattedValue(row, column) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
