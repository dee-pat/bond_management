<script setup lang="ts">
import { computed, isRef, onBeforeUnmount, ref, watch } from "vue";
import { ChartCard, LineChart, paletteColors, useChartTheme } from "frappe-ui/charts";
import type { ChartTooltipItem, LineChartProps, SeriesStyle } from "frappe-ui/charts";
import type { ECharts } from "echarts/core";

import { formatDate, formatNumber, formatPercent } from "../lib/format";
import type { YieldComparisonRow } from "../report-types";

interface YieldPoint {
	date: string;
	row: YieldComparisonRow;
	value: number;
}

interface YieldSeries {
	isin: string;
	currency: string;
}

const props = defineProps<{
	rows: YieldComparisonRow[];
	marketPricePrecision: number;
	futureXirrPrecision: number;
}>();

const Y_TICK_STEP = 5;
const chartRoot = ref<HTMLElement>();
const lineChartRef = ref<{ chart?: unknown } | null>(null);
const hoveredIsin = ref<string | null>(null);
const { theme } = useChartTheme(chartRoot);
let boundChart: ECharts | undefined;
const dates = computed(() => [...new Set(props.rows.map((row) => row.date))].sort());
const currencies = computed(() =>
	[...new Set(props.rows.map((row) => row.currency))].sort((left, right) =>
		left.localeCompare(right)
	)
);
const currencyColors = computed(() => {
	const colors = paletteColors("categorical", theme.value, currencies.value.length);
	return new Map(currencies.value.map((currency, index) => [currency, colors[index]]));
});
const series = computed<YieldSeries[]>(() => {
	const currencies = new Map<string, string>();
	props.rows.forEach((row) => {
		if (!currencies.has(row.isin)) {
			currencies.set(row.isin, row.currency);
		}
	});

	return [...currencies.entries()]
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([isin, currency]) => ({ isin, currency }));
});
const rowsByKey = computed(() => {
	const rows = new Map<string, YieldComparisonRow>();
	props.rows.forEach((row) => {
		rows.set(pointKey(row.isin, row.date), row);
	});
	return rows;
});
const points = computed<YieldPoint[]>(() =>
	series.value.flatMap((item) =>
		dates.value.flatMap((date) => {
			const row = rowsByKey.value.get(pointKey(item.isin, date));
			const value = numericValue(row?.future_xirr);
			return row && value !== null ? [{ date, row, value }] : [];
		})
	)
);
const pointCountByIsin = computed(() => {
	const counts = new Map<string, number>();
	points.value.forEach((point) => {
		counts.set(point.row.isin, (counts.get(point.row.isin) ?? 0) + 1);
	});
	return counts;
});
const gapCount = computed(() =>
	series.value.reduce(
		(total, item) => total + dates.value.length - (pointCountByIsin.value.get(item.isin) ?? 0),
		0
	)
);
// This time-series view uses zero and 5-point ticks so values stay comparable
// across the selected market-date range.
const yDomain = computed(() => getPercentAxisDomain(points.value.map((point) => point.value)));
const seriesConfig = computed<Record<string, SeriesStyle>>(() =>
	Object.fromEntries(
		series.value.map((item) => [
			item.isin,
			{
				label: `${item.isin} · ${item.currency}`,
				color: currencyColors.value.get(item.currency),
				showDataPoints: true,
				// ECharts only forwards mouse events from a line path when this
				// option is enabled. The Desk chart listens on each path, so keep
				// the same line-level hit target for the per-bond tooltip.
				echartOptions: { triggerLineEvent: true },
			},
		])
	)
);
const chartProps = computed<LineChartProps>(() => ({
	data: dates.value.flatMap((date) =>
		series.value.map((item) => ({
			date,
			isin: item.isin,
			future_xirr: numericValue(rowsByKey.value.get(pointKey(item.isin, date))?.future_xirr),
		}))
	),
	x: "date",
	y: "future_xirr",
	series: "isin",
	title: "Persisted Future XIRR",
	subtitle: "By market date and bond",
	palette: "categorical",
	seriesConfig: seriesConfig.value,
	xAxis: {
		type: "category",
		title: "Market date",
		format: (value) => formatMarketDate(String(value)),
	},
	yAxis: {
		title: "Future XIRR (%)",
		min: yDomain.value.minimum,
		max: yDomain.value.maximum,
		format: (value) => formatPercent(value, props.futureXirrPrecision),
		echartOptions: { interval: Y_TICK_STEP },
	},
}));
const accessibleDescription = computed(() => points.value.map(pointLabel).join("; "));

const chartInstance = computed<ECharts | undefined>(() => {
	const chart = lineChartRef.value?.chart;
	return isRef(chart) ? (chart.value as ECharts | undefined) : (chart as ECharts | undefined);
});

// The shared line chart uses an axis tooltip, which includes every visible
// series at the current date. Track the hovered ECharts series only to narrow
// this app's tooltip slot to the bond under the pointer.
watch(chartInstance, (chart) => {
	if (boundChart === chart) {
		return;
	}
	if (boundChart) {
		boundChart.off("mouseover", handleChartMouseOver);
		boundChart.off("mouseout", clearHoveredIsin);
	}
	boundChart = chart;
	if (boundChart) {
		boundChart.on("mouseover", handleChartMouseOver);
		boundChart.on("mouseout", clearHoveredIsin);
	}
});

onBeforeUnmount(() => {
	if (boundChart) {
		boundChart.off("mouseover", handleChartMouseOver);
		boundChart.off("mouseout", clearHoveredIsin);
	}
});

function pointKey(isin: string, date: string): string {
	return `${isin}\u0000${date}`;
}

function numericValue(value: unknown): number | null {
	if (value === null || value === undefined || value === "") {
		return null;
	}
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

function pointLabel(point: YieldPoint): string {
	const marketPrice = numericValue(point.row.market_price);
	return `${formatDate(point.date)}, ${point.row.isin}, ${point.row.currency}, Market Price ${
		marketPrice === null ? "—" : formatNumber(marketPrice, props.marketPricePrecision)
	}, Future XIRR ${formatPercent(point.value, props.futureXirrPrecision)}`;
}

function formatMarketDate(value: string): string {
	const parts = formatDate(value).split(" ");
	return parts.length === 3 ? `${parts.slice(0, 2).join(" ")}\n${parts[2]}` : formatDate(value);
}

function visibleTooltipItems(items: ChartTooltipItem[], label?: string): ChartTooltipItem[] {
	const date = dates.value.find((candidate) => formatMarketDate(candidate) === label);

	return items.filter((item) => {
		if (hoveredIsin.value && item.name !== hoveredIsin.value) {
			return false;
		}

		const row = date ? rowsByKey.value.get(pointKey(item.name, date)) : undefined;
		return row ? numericValue(row.future_xirr) !== null : false;
	});
}

function handleChartMouseOver(params: unknown): void {
	if (params && typeof params === "object" && "seriesName" in params) {
		const seriesName = params.seriesName;
		if (typeof seriesName === "string") {
			hoveredIsin.value = seriesName;
		}
	}
}

function clearHoveredIsin(): void {
	hoveredIsin.value = null;
}

function getPercentAxisDomain(values: number[]): { minimum: number; maximum: number } {
	if (!values.length) {
		return { minimum: 0, maximum: Y_TICK_STEP };
	}

	const minimumValue = Math.min(...values);
	const maximumValue = Math.max(...values);
	const minimum = Math.floor(Math.min(minimumValue, 0) / Y_TICK_STEP) * Y_TICK_STEP;
	let maximum = Math.ceil(Math.max(maximumValue, 0) / Y_TICK_STEP) * Y_TICK_STEP;
	if (maximum <= minimum || maximum === maximumValue) {
		maximum += Y_TICK_STEP;
	}
	return { minimum, maximum };
}
</script>

<template>
	<section
		ref="chartRoot"
		class="yield-comparison-chart"
		data-testid="yield-comparison-chart"
		:data-gap-count="gapCount"
		aria-describedby="yield-comparison-chart-description"
		aria-label="Bond yield comparison chart"
		role="region"
	>
		<ChartCard class="yield-comparison-chart__card">
			<LineChart ref="lineChartRef" v-bind="chartProps">
				<template #tooltip="{ label, items }">
					<div v-if="label" class="mb-2 text-p-sm text-ink-gray-5">{{ label }}</div>
					<div
						class="flex flex-col gap-1.5"
						data-testid="yield-comparison-chart-tooltip"
					>
						<div
							v-for="item in visibleTooltipItems(items, label)"
							:key="item.name"
							class="flex items-center justify-between gap-5 text-p-sm"
						>
							<span class="min-w-0 truncate text-ink-gray-6">{{ item.label }}</span>
							<span class="shrink-0 text-p-sm-semibold tabular-nums text-ink-gray-8">
								ISIN {{ item.name }} · Future XIRR {{ item.formattedValue }}
							</span>
						</div>
					</div>
				</template>
			</LineChart>
			<p
				id="yield-comparison-chart-description"
				class="yield-comparison-chart__description sr-only"
				data-testid="yield-comparison-chart-description"
			>
				{{ accessibleDescription }}
			</p>
		</ChartCard>
	</section>
</template>
