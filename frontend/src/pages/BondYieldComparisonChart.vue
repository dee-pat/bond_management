<script setup lang="ts">
import { computed } from "vue";

import { formatDate, formatNumber, formatPercent } from "../lib/format";
import type { YieldComparisonRow } from "../report-types";

interface YieldPoint {
	date: string;
	dateIndex: number;
	row: YieldComparisonRow;
	value: number;
}

interface YieldSeries {
	isin: string;
	currency: string;
	color: string;
	points: YieldPoint[];
	segments: YieldPoint[][];
}

interface YearTick {
	year: string;
	dateIndex: number;
}

const props = defineProps<{
	rows: YieldComparisonRow[];
	selectedIsins: string[];
	marketPricePrecision: number;
	futureXirrPrecision: number;
}>();
const currencyColors: Record<string, string> = {
	USD: "#5e64ff",
	KES: "#28a745",
	EUR: "#ff5858",
	GBP: "#f39c12",
	JPY: "#8e44ad",
	ZAR: "#00a6a6",
	CHF: "#d35400",
};
const fallbackColors = ["#2563eb", "#db2777", "#059669", "#d97706", "#7c3aed", "#dc2626"];
const width = 900;
const height = 360;
const margin = { top: 24, right: 24, bottom: 70, left: 72 };
const plotWidth = width - margin.left - margin.right;
const plotHeight = height - margin.top - margin.bottom;
const yTickIndexes = [0, 1, 2, 3, 4];

const dates = computed(() => [...new Set(props.rows.map((row) => row.date))].sort());
const selected = computed(() => new Set(props.selectedIsins));
const series = computed<YieldSeries[]>(() => {
	const isins = [...new Set(props.rows.map((row) => row.isin))]
		.filter((isin) => selected.value.has(isin))
		.sort();
	return isins.map((isin) => buildSeries(isin));
});
const points = computed(() => series.value.flatMap((item) => item.points));
const yearTicks = computed<YearTick[]>(() => {
	const indexesByYear = new Map<string, number[]>();
	dates.value.forEach((date, dateIndex) => {
		const year = date.slice(0, 4);
		indexesByYear.set(year, [...(indexesByYear.get(year) ?? []), dateIndex]);
	});
	return [...indexesByYear].map(([year, indexes]) => ({
		year,
		dateIndex: (indexes[0] + indexes[indexes.length - 1]) / 2,
	}));
});
const gapCount = computed(() =>
	series.value.reduce(
		(total, item) => total + Math.max(dates.value.length - item.points.length, 0),
		0
	)
);
const yDomain = computed(() => {
	const values = points.value.map((point) => point.value);
	const minimum = Math.min(...values);
	const maximum = Math.max(...values);
	const padding =
		minimum === maximum
			? Math.max(Math.abs(minimum) * 0.1, 1)
			: Math.max((maximum - minimum) * 0.1, 0.25);
	return { minimum: minimum - padding, maximum: maximum + padding };
});

function buildSeries(isin: string): YieldSeries {
	const rowsByDate = new Map(
		props.rows.filter((row) => row.isin === isin).map((row) => [row.date, row])
	);
	const pointsByDate = dates.value.map((date, dateIndex) => {
		const row = rowsByDate.get(date);
		const value = numericValue(row?.future_xirr);
		return row && value !== null ? { date, dateIndex, row, value } : null;
	});
	const firstRow = props.rows.find((row) => row.isin === isin);
	const currency = firstRow?.currency ?? "";
	return {
		isin,
		currency,
		color: colorForCurrency(currency),
		points: pointsByDate.filter((point): point is YieldPoint => point !== null),
		segments: splitSegments(pointsByDate),
	};
}

function colorForCurrency(currency: string): string {
	if (currencyColors[currency]) {
		return currencyColors[currency];
	}
	const currencies = [...new Set(props.rows.map((row) => row.currency))].sort();
	const colorIndex = Math.max(currencies.indexOf(currency), 0) % fallbackColors.length;
	return fallbackColors[colorIndex];
}

function splitSegments(pointsByDate: Array<YieldPoint | null>): YieldPoint[][] {
	const segments: YieldPoint[][] = [];
	let current: YieldPoint[] = [];
	pointsByDate.forEach((point) => {
		if (point) {
			current.push(point);
			return;
		}
		if (current.length) {
			segments.push(current);
			current = [];
		}
	});
	if (current.length) {
		segments.push(current);
	}
	return segments;
}

function numericValue(value: unknown): number | null {
	if (value === null || value === undefined || value === "") {
		return null;
	}
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

function xPosition(dateIndex: number): number {
	return margin.left + (dateIndex / Math.max(dates.value.length - 1, 1)) * plotWidth;
}

function yPosition(value: number): number {
	const domain = yDomain.value;
	return (
		margin.top + ((domain.maximum - value) / (domain.maximum - domain.minimum)) * plotHeight
	);
}

function yTickValue(index: number): number {
	const ratio = index / (yTickIndexes.length - 1);
	return yDomain.value.maximum - (yDomain.value.maximum - yDomain.value.minimum) * ratio;
}

function linePoints(segment: YieldPoint[]): string {
	return segment
		.map((point) => `${xPosition(point.dateIndex)},${yPosition(point.value)}`)
		.join(" ");
}

function pointLabel(point: YieldPoint): string {
	const marketPrice = numericValue(point.row.market_price);
	return `${formatDate(point.date)}, ${point.row.isin}, ${point.row.currency}, Market Price ${
		marketPrice === null ? "—" : formatNumber(marketPrice, props.marketPricePrecision)
	}, Future XIRR ${formatPercent(point.value, props.futureXirrPrecision)}`;
}

const accessibleDescription = computed(() => points.value.map(pointLabel).join("; "));
</script>

<template>
	<section
		class="yield-comparison-chart"
		data-testid="yield-comparison-chart"
		:data-gap-count="gapCount"
	>
		<div aria-label="Bond yield series" class="yield-comparison-chart__legend" role="list">
			<span v-for="item in series" :key="item.isin" role="listitem">
				<i :style="{ backgroundColor: item.color }" aria-hidden="true" />
				{{ item.isin }} · {{ item.currency }}
			</span>
		</div>

		<p id="yield-comparison-chart-description" class="yield-comparison-chart__description">
			{{ accessibleDescription }}
		</p>

		<svg
			:viewBox="`0 0 ${width} ${height}`"
			aria-describedby="yield-comparison-chart-description"
			aria-label="Persisted Future XIRR by market date and bond"
			role="img"
		>
			<title>Bond Yield Comparison</title>

			<g v-for="index in yTickIndexes" :key="`yield-tick-${index}`">
				<line
					:x1="margin.left"
					:x2="margin.left + plotWidth"
					:y1="yPosition(yTickValue(index))"
					:y2="yPosition(yTickValue(index))"
					class="yield-comparison-chart__gridline"
				/>
				<text
					:x="margin.left - 10"
					:y="yPosition(yTickValue(index)) + 4"
					text-anchor="end"
				>
					{{ formatPercent(yTickValue(index), futureXirrPrecision) }}
				</text>
			</g>

			<line
				:x1="margin.left"
				:x2="margin.left"
				:y1="margin.top"
				:y2="margin.top + plotHeight"
				class="yield-comparison-chart__axis"
			/>
			<line
				:x1="margin.left"
				:x2="margin.left + plotWidth"
				:y1="margin.top + plotHeight"
				:y2="margin.top + plotHeight"
				class="yield-comparison-chart__axis"
			/>

			<g v-for="tick in yearTicks" :key="tick.year" data-testid="yield-comparison-year-tick">
				<line
					:x1="xPosition(tick.dateIndex)"
					:x2="xPosition(tick.dateIndex)"
					:y1="margin.top + plotHeight"
					:y2="margin.top + plotHeight + 5"
					class="yield-comparison-chart__axis"
				/>
				<text
					:x="xPosition(tick.dateIndex)"
					:y="margin.top + plotHeight + 18"
					text-anchor="middle"
				>
					{{ tick.year }}
				</text>
			</g>

			<g v-for="item in series" :key="item.isin">
				<polyline
					v-for="(segment, index) in item.segments"
					:key="`${item.isin}-segment-${index}`"
					:points="linePoints(segment)"
					:stroke="item.color"
					class="yield-comparison-chart__line"
				/>
			</g>

			<text
				:x="margin.left + plotWidth / 2"
				:y="height - 7"
				class="yield-comparison-chart__axis-label"
				text-anchor="middle"
			>
				Year
			</text>
			<text
				:transform="`translate(18 ${margin.top + plotHeight / 2}) rotate(-90)`"
				class="yield-comparison-chart__axis-label"
				text-anchor="middle"
			>
				Future XIRR (%)
			</text>
		</svg>
	</section>
</template>
