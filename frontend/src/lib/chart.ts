import { computed, isRef, onBeforeUnmount, watch, type Ref } from "vue";
import type { ECharts } from "echarts/core";

/**
 * Bind ECharts mouseover/mouseout handlers to a frappe-ui LineChart and rebind
 * them whenever the chart instance is recreated.
 */
export function useChartHover(
	lineChartRef: Ref<{ chart?: unknown } | null>,
	onMouseOver: (params: unknown) => void,
	onMouseOut: () => void
): void {
	const chartInstance = computed<ECharts | undefined>(() => {
		const chart = lineChartRef.value?.chart;
		return isRef(chart) ? (chart.value as ECharts | undefined) : (chart as ECharts | undefined);
	});
	let boundChart: ECharts | undefined;

	function bind(chart: ECharts | undefined): void {
		boundChart?.off("mouseover", onMouseOver);
		boundChart?.off("mouseout", onMouseOut);
		boundChart = chart;
		boundChart?.on("mouseover", onMouseOver);
		boundChart?.on("mouseout", onMouseOut);
	}

	watch(chartInstance, (chart) => {
		if (chart !== boundChart) bind(chart);
	});
	onBeforeUnmount(() => bind(undefined));
}
