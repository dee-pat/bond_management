<script setup lang="ts">
import { Button } from "frappe-ui";
import { RouterLink } from "vue-router";

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
	isin: "12rem",
	currency: "4.5rem",
	principal_factor: "8rem",
	nominal_value: "10rem",
	purchases_value: "10rem",
	proceeds_value: "10rem",
	market_value: "10rem",
	market_value_usd: "11rem",
	gain_value: "10rem",
	xirr: "8rem",
	xirr_usd: "9rem",
	future_xirr: "9.5rem",
	expected_coupons_next_year: "13rem",
	expected_coupons_next_year_usd: "15rem",
};

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

function isNumericColumn(column: PerformanceColumn): boolean {
	return column.fieldname !== "isin" && column.fieldname !== "currency";
}

function actionFor(
	row: PerformanceRow,
	column: PerformanceColumn
): PerformanceCashflowSelection | null {
	const action = column.cashflow_action;
	if (
		!action ||
		!row[action.xirr_type === "past" ? "has_past_cashflows" : "has_future_cashflows"] ||
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
		<table data-testid="performance-table" class="performance-table">
			<colgroup>
				<col
					v-for="column in props.columns"
					:key="column.fieldname"
					:style="{ width: PERFORMANCE_COLUMN_WIDTHS[column.fieldname] }"
				/>
			</colgroup>
			<thead>
				<tr>
					<th
						v-for="column in props.columns"
						:key="column.fieldname"
						:class="{ 'performance-table__numeric': isNumericColumn(column) }"
						:title="column.description ?? undefined"
						scope="col"
					>
						{{ column.label }}
					</th>
				</tr>
			</thead>
			<tbody>
				<tr
					v-for="row in props.rows"
					:key="row.isin"
					data-testid="performance-row"
					:class="{ 'performance-table__total': row.isin === 'TOTAL' }"
				>
					<td
						v-for="column in props.columns"
						:key="column.fieldname"
						:class="{ 'performance-table__numeric': isNumericColumn(column) }"
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
							:label="`Copy ${
								actionFor(row, column)?.cashflow_currency
							} cash flows for ${row.isin} ${column.label}`"
							@click="emit('copy', actionFor(row, column)!)"
						>
							{{ formattedValue(row, column) || "Copy cash flows" }}
						</Button>
						<span v-else>{{ formattedValue(row, column) }}</span>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>
