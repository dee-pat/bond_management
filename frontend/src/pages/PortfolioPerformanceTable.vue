<script setup lang="ts">
import { computed } from "vue";
import { Button } from "frappe-ui";
import { ListCell, ListHeaderCell } from "frappe-ui/list";
import { RouterLink } from "vue-router";

import DataList from "../components/DataList.vue";
import { formatMoney, formatNumber, formatPercent } from "../lib/format";
import type {
	PerformanceCashflowSelection,
	PerformanceColumn,
	PerformanceFieldname,
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

const PERFORMANCE_COLUMN_WIDTHS: Record<PerformanceFieldname, string> = {
	isin: "minmax(12rem, 1.25fr)",
	currency: "minmax(4.5rem, 0.6fr)",
	principal_factor: "minmax(8rem, 0.9fr)",
	nominal_value: "minmax(10rem, 1fr)",
	purchases_value: "minmax(10rem, 1fr)",
	proceeds_value: "minmax(10rem, 1fr)",
	market_value: "minmax(10rem, 1fr)",
	market_value_usd: "minmax(11rem, 1fr)",
	gain_value: "minmax(10rem, 1fr)",
	xirr: "minmax(8rem, 0.75fr)",
	xirr_usd: "minmax(9rem, 0.8fr)",
	future_xirr: "minmax(9.5rem, 0.85fr)",
};

const listColumns = computed(() =>
	props.columns.map((column) => PERFORMANCE_COLUMN_WIDTHS[column.fieldname])
);

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
		return formatMoney(value, currencyFor(row, column), precision);
	}
	if (column.fieldtype === "Percent") {
		return formatPercent(value, precision);
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
	<DataList
		:items="props.rows"
		:columns="listColumns"
		row-key="isin"
		row-test-id="performance-row"
		data-testid="performance-table"
		class="performance-table-wrap"
	>
		<template #header>
			<ListHeaderCell
				v-for="column in props.columns"
				:key="column.fieldname"
				:class="{
					'justify-end': column.fieldname !== 'isin' && column.fieldname !== 'currency',
				}"
				:title="column.description ?? undefined"
			>
				{{ column.label }}
			</ListHeaderCell>
		</template>
		<template #row="{ item: row }">
			<ListCell
				v-for="column in props.columns"
				:key="column.fieldname"
				:data-label="column.label"
				:class="[
					{
						'justify-end':
							column.fieldname !== 'isin' && column.fieldname !== 'currency',
					},
					{ 'performance-table__total': row.isin === 'TOTAL' },
				]"
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
				<Button
					v-else-if="actionFor(row, column)"
					class="performance-cashflow-button"
					variant="ghost"
					size="sm"
					:disabled="copyingKey !== null"
					:label="`Copy ${actionFor(row, column)?.cashflow_currency} cash flows for ${
						row.isin
					} ${column.label}`"
					@click="emit('copy', actionFor(row, column)!)"
				>
					{{ formattedValue(row, column) }}
				</Button>
				<span v-else>{{ formattedValue(row, column) }}</span>
			</ListCell>
		</template>
	</DataList>
</template>
