<script setup lang="ts">
import { computed } from "vue";

import { formatDate, formatNumber, formatPercent } from "../lib/format";
import type { MarketPriceRow } from "../types";

interface YieldPoint {
	isin: string;
	currency: string;
	repaymentDate: string;
	years: number;
	yieldPercent: number;
}

interface YieldSeries {
	currency: string;
	color: string;
	points: YieldPoint[];
}

const props = defineProps<{ rows: MarketPriceRow[] }>();
const colors = ["#2563eb", "#db2777", "#059669", "#d97706", "#7c3aed", "#dc2626"];
const width = 900;
const height = 340;
const margin = { top: 24, right: 24, bottom: 58, left: 72 };
const plotWidth = width - margin.left - margin.right;
const plotHeight = height - margin.top - margin.bottom;
const tickIndexes = [0, 1, 2, 3, 4];

const points = computed<YieldPoint[]>(() =>
	props.rows
		.flatMap((row) => {
			const years = Number(row.weighted_avg_repayment_years);
			const yieldPercent = Number(row.future_xirr);
			if (
				!row.isin ||
				!row.currency ||
				!row.weighted_avg_repayment_date ||
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
		.sort((left, right) => left.years - right.years)
);

const series = computed<YieldSeries[]>(() => {
	const grouped = new Map<string, YieldPoint[]>();
	points.value.forEach((point) => {
		grouped.set(point.currency, [...(grouped.get(point.currency) ?? []), point]);
	});
	return [...grouped.entries()]
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([currency, currencyPoints], index) => ({
			currency,
			color: colors[index % colors.length],
			points: currencyPoints,
		}));
});

const xMaximum = computed(() => Math.max(...points.value.map((point) => point.years), 1));
const yDomain = computed(() => {
	const yields = points.value.map((point) => point.yieldPercent);
	const minimum = Math.min(...yields);
	const maximum = Math.max(...yields);
	const padding =
		minimum === maximum
			? Math.max(Math.abs(minimum) * 0.1, 1)
			: Math.max((maximum - minimum) * 0.1, 0.25);
	return { minimum: minimum - padding, maximum: maximum + padding };
});

function xPosition(years: number): number {
	return margin.left + (years / xMaximum.value) * plotWidth;
}

function yPosition(yieldPercent: number): number {
	const domain = yDomain.value;
	return (
		margin.top +
		((domain.maximum - yieldPercent) / (domain.maximum - domain.minimum)) * plotHeight
	);
}

function xTickValue(index: number): number {
	return xMaximum.value * (index / (tickIndexes.length - 1));
}

function yTickValue(index: number): number {
	const ratio = index / (tickIndexes.length - 1);
	return yDomain.value.maximum - (yDomain.value.maximum - yDomain.value.minimum) * ratio;
}

function linePoints(currencyPoints: YieldPoint[]): string {
	return currencyPoints
		.map((point) => `${xPosition(point.years)},${yPosition(point.yieldPercent)}`)
		.join(" ");
}

function pointLabel(point: YieldPoint): string {
	return `${point.isin}, ${point.currency}, ${formatPercent(point.yieldPercent)}, ${formatDate(
		point.repaymentDate
	)}, ${formatNumber(point.years, 2)} years`;
}
</script>

<template>
	<section class="yield-curve-section">
		<h3>Yield Curve</h3>
		<div v-if="points.length === 0" class="surface-state" data-testid="yield-curve-empty">
			No valid yield-curve data.
		</div>
		<div v-else class="yield-curve" data-testid="yield-curve">
			<div class="yield-curve__legend" aria-label="Yield curve currencies" role="list">
				<span v-for="item in series" :key="item.currency" role="listitem">
					<i :style="{ backgroundColor: item.color }" aria-hidden="true" />
					{{ item.currency }}
				</span>
			</div>

			<svg
				:viewBox="`0 0 ${width} ${height}`"
				role="img"
				aria-label="Yield curve by currency and weighted average principal repayment"
			>
				<title>Yield Curve</title>

				<g v-for="index in tickIndexes" :key="`tick-${index}`">
					<line
						:x1="margin.left"
						:x2="margin.left + plotWidth"
						:y1="yPosition(yTickValue(index))"
						:y2="yPosition(yTickValue(index))"
						class="yield-curve__gridline"
					/>
					<text
						:x="margin.left - 10"
						:y="yPosition(yTickValue(index)) + 4"
						text-anchor="end"
					>
						{{ formatPercent(yTickValue(index)) }}
					</text>
					<line
						:x1="xPosition(xTickValue(index))"
						:x2="xPosition(xTickValue(index))"
						:y1="margin.top + plotHeight"
						:y2="margin.top + plotHeight + 5"
						class="yield-curve__axis"
					/>
					<text
						:x="xPosition(xTickValue(index))"
						:y="margin.top + plotHeight + 20"
						text-anchor="middle"
					>
						{{ formatNumber(xTickValue(index), 2) }}
					</text>
				</g>

				<line
					:x1="margin.left"
					:x2="margin.left"
					:y1="margin.top"
					:y2="margin.top + plotHeight"
					class="yield-curve__axis"
				/>
				<line
					:x1="margin.left"
					:x2="margin.left + plotWidth"
					:y1="margin.top + plotHeight"
					:y2="margin.top + plotHeight"
					class="yield-curve__axis"
				/>

				<g v-for="item in series" :key="`series-${item.currency}`">
					<polyline
						:points="linePoints(item.points)"
						:stroke="item.color"
						class="yield-curve__line"
					/>
					<circle
						v-for="point in item.points"
						:key="`${point.isin}-${point.years}`"
						:cx="xPosition(point.years)"
						:cy="yPosition(point.yieldPercent)"
						:fill="item.color"
						:aria-label="pointLabel(point)"
						class="yield-curve__point"
						r="7"
						tabindex="0"
					>
						<title>{{ pointLabel(point) }}</title>
					</circle>
				</g>

				<text
					:x="margin.left + plotWidth / 2"
					:y="height - 8"
					class="yield-curve__axis-label"
					text-anchor="middle"
				>
					Weighted average principal repayment years
				</text>
				<text
					:transform="`translate(18 ${margin.top + plotHeight / 2}) rotate(-90)`"
					class="yield-curve__axis-label"
					text-anchor="middle"
				>
					Future XIRR (%)
				</text>
			</svg>
		</div>
	</section>
</template>
