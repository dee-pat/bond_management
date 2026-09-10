<script setup lang="ts">
import { computed, isRef, onBeforeUnmount, ref, watch } from "vue";
import { ChartCard, LineChart } from "frappe-ui/charts";
import type { ChartTooltipItem, LineChartProps, SeriesStyle } from "frappe-ui/charts";
import type { ECharts } from "echarts/core";

import { formatDate, formatNumber, formatPercent } from "../lib/format";
import type { MarketPriceRow } from "../types";

interface YieldPoint {
	isin: string;
	currency: string;
	repaymentDate: string;
	years: number;
	yieldPercent: number;
}

const props = defineProps<{ rows: MarketPriceRow[] }>();
const lineChartRef = ref<{ chart?: unknown } | null>(null);
const hoveredPoint = ref<YieldPoint | null>(null);
let boundChart: ECharts | undefined;

const points = computed<YieldPoint[]>(() =>
	props.rows
		.flatMap((row) => {
			const years = Number(row.weighted_avg_repayment_years);
			const yieldPercent = Number(row.future_xirr);
			if (
				!row.isin ||
				!row.currency ||
				!row.weighted_avg_repayment_date ||
				row.future_xirr === null ||
				row.future_xirr === undefined ||
				!Number.isFinite(years) ||
				years <= 0 ||
				!Number.isFinite(yieldPercent)
			) {
				return [];
			}
			return [
				{
					isin: row.isin,
					currency: row.currency,
					repaymentDate: row.weighted_avg_repayment_date,
					years,
					yieldPercent,
				},
			];
		})
		.sort((left, right) => left.years - right.years || left.isin.localeCompare(right.isin))
);
const currencies = computed(() =>
	[...new Set(points.value.map((point) => point.currency))].sort()
);
// Keep one wide row per bond. The chart's long-data pivot would overwrite
// bonds that share both a currency and a repayment duration.
const chartData = computed(() =>
	points.value.map((point) => ({
		years: point.years,
		[point.currency]: point.yieldPercent,
	}))
);
const xMaximum = computed(() => Math.max(...points.value.map((point) => point.years), 1));
const yDomain = computed(() =>
	getPercentAxisDomain(points.value.map((point) => point.yieldPercent))
);
const seriesConfig = computed<Record<string, SeriesStyle>>(() =>
	Object.fromEntries(
		currencies.value.map((currency) => [
			currency,
			{
				label: currency,
				lineWidth: 2.5,
				showDataPoints: true,
				// Keep line hits tied to the point so the tooltip can identify its bond.
				echartOptions: { triggerLineEvent: true },
			},
		])
	)
);
const chartProps = computed<LineChartProps>(() => ({
	data: chartData.value,
	x: "years",
	y: currencies.value,
	// Wide data keeps every bond row while the value columns remain one series
	// per currency. Nulls are only between points from different currencies.
	connectNulls: true,
	title: "Yield Curve",
	palette: "categorical",
	seriesConfig: seriesConfig.value,
	xAxis: {
		type: "value",
		title: "Years to weighted average principal repayment",
		min: 0,
		max: xMaximum.value,
		format: (value) => formatYears(value),
	},
	yAxis: {
		title: "Yield (%)",
		min: yDomain.value.minimum,
		max: yDomain.value.maximum,
		format: (value) => formatPercent(value, 2),
	},
}));
const accessibleDescription = computed(() => points.value.map(pointLabel).join("; "));
const chartInstance = computed<ECharts | undefined>(() => {
	const chart = lineChartRef.value?.chart;
	return isRef(chart) ? (chart.value as ECharts | undefined) : (chart as ECharts | undefined);
});

watch(chartInstance, (chart) => {
	if (boundChart === chart) {
		return;
	}
	if (boundChart) {
		boundChart.off("mouseover", handleChartMouseOver);
		boundChart.off("mouseout", clearHoveredPoint);
	}
	boundChart = chart;
	if (boundChart) {
		boundChart.on("mouseover", handleChartMouseOver);
		boundChart.on("mouseout", clearHoveredPoint);
	}
});

onBeforeUnmount(() => {
	if (boundChart) {
		boundChart.off("mouseover", handleChartMouseOver);
		boundChart.off("mouseout", clearHoveredPoint);
	}
});

function pointLabel(point: YieldPoint): string {
	return `${point.isin}, ${point.currency}, ${formatPercent(point.yieldPercent)}, ${formatDate(
		point.repaymentDate
	)}, ${formatNumber(point.years, 2)} years`;
}

function formatYears(value: number): string {
	return `${formatNumber(value, value >= 10 ? 1 : 2)}y`;
}

function visibleTooltipItems(items: ChartTooltipItem[]): ChartTooltipItem[] {
	return hoveredPoint.value
		? items.filter((item) => item.name === hoveredPoint.value?.currency)
		: items;
}

function handleChartMouseOver(params: unknown): void {
	if (!params || typeof params !== "object") {
		clearHoveredPoint();
		return;
	}

	const seriesName = "seriesName" in params ? params.seriesName : undefined;
	const dataIndex = "dataIndex" in params ? params.dataIndex : undefined;
	if (
		typeof seriesName !== "string" ||
		typeof dataIndex !== "number" ||
		!Number.isInteger(dataIndex)
	) {
		clearHoveredPoint();
		return;
	}

	const point = points.value[dataIndex];
	if (!point || point.currency !== seriesName) {
		clearHoveredPoint();
		return;
	}
	hoveredPoint.value = point;
}

function clearHoveredPoint(): void {
	hoveredPoint.value = null;
}

function getPercentAxisDomain(values: number[]): { minimum: number; maximum: number } {
	if (!values.length) return { minimum: 0, maximum: 1 };

	const minimumValue = Math.min(...values);
	const maximumValue = Math.max(...values);
	const padding =
		minimumValue === maximumValue
			? Math.max(Math.abs(minimumValue) * 0.1, 1)
			: Math.max((maximumValue - minimumValue) * 0.1, 0.25);
	return {
		minimum: minimumValue - padding,
		maximum: maximumValue + padding,
	};
}
</script>

<template>
	<section
		class="yield-curve-section"
		:aria-describedby="points.length ? 'yield-curve-description' : undefined"
		aria-label="Yield curve chart"
		role="region"
	>
		<ChartCard class="yield-curve" data-testid="yield-curve">
			<LineChart ref="lineChartRef" v-bind="chartProps">
				<template #tooltip="{ label, items }">
					<div v-if="label" class="mb-2 text-p-sm text-ink-gray-5">{{ label }}</div>
					<div class="flex flex-col gap-1.5" data-testid="yield-curve-tooltip">
						<div
							v-for="item in visibleTooltipItems(items)"
							:key="item.name"
							class="flex items-center justify-between gap-5 text-p-sm"
						>
							<span class="min-w-0 truncate text-ink-gray-6">{{ item.label }}</span>
							<span
								v-if="hoveredPoint && hoveredPoint.currency === item.name"
								class="shrink-0 text-p-sm-semibold tabular-nums text-ink-gray-8"
							>
								ISIN {{ hoveredPoint.isin }} · Yield
								{{ formatPercent(hoveredPoint.yieldPercent, 2) }}
							</span>
							<span
								v-else
								class="shrink-0 text-p-sm-semibold tabular-nums text-ink-gray-8"
							>
								{{ item.formattedValue }}
							</span>
						</div>
					</div>
				</template>
				<template #empty>
					<span class="text-p-sm text-ink-gray-5" data-testid="yield-curve-empty">
						No valid yield-curve data.
					</span>
				</template>
			</LineChart>
			<p
				id="yield-curve-description"
				class="yield-curve__description sr-only"
				data-testid="yield-curve-description"
			>
				{{ accessibleDescription }}
			</p>
		</ChartCard>
	</section>
</template>
