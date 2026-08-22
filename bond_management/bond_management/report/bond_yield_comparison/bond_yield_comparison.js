// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

const CURRENCY_COLORS_BY_CODE = {
	USD: "#5e64ff",
	KES: "#28a745",
	EUR: "#ff5858",
	GBP: "#f39c12",
	JPY: "#8e44ad",
	ZAR: "#00a6a6",
	CHF: "#d35400",
};
const FALLBACK_CURRENCY_COLORS = ["#5e64ff", "#28a745", "#ff5858", "#f39c12", "#8e44ad"];
const GAP_CHART_LAYOUT = {
	width: 1000,
	left: 82,
	right: 24,
	top: 38,
	bottom: 286,
};

frappe.query_reports["Bond Yield Comparison"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
		},
	],

	get_chart_data(columns, result) {
		return make_frappe_chart_options(build_chart_model(result));
	},

	after_refresh(report) {
		remove_report_controls(report);
		if (report.raw_data?.result?.length) {
			report.$report.hide();
			const model = build_chart_model(report.raw_data.result);
			initialize_selected_bonds(report, model);
			render_bond_yield_chart(report, model);
			render_bond_selector(report, model);
			render_audit_copy_button(report);
		}
	},
};

function build_chart_model(result) {
	const rows = result.filter((row) => row && Object.keys(row).length);
	const dates = [...new Set(rows.map((row) => date_key(row.date)).filter(Boolean))].sort();
	const bonds = [...new Set(rows.map((row) => row.isin).filter(Boolean))].sort();
	const date_index = new Map(dates.map((date, index) => [date, index]));
	const rows_by_bond_date = new Map(
		rows.map((row) => [`${row.isin}::${date_key(row.date)}`, row])
	);
	const currency_by_bond = new Map(
		bonds.map((isin) => [isin, rows.find((row) => row.isin === isin)?.currency || ""])
	);
	const currency_colors = create_currency_colors(currency_by_bond);
	const datasets = bonds.map((isin) => {
		const currency = currency_by_bond.get(isin);
		return {
			name: isin,
			isin,
			values: dates.map((date) =>
				parse_xirr(rows_by_bond_date.get(`${isin}::${date}`)?.future_xirr)
			),
			currency,
			color: currency_colors.get(currency),
		};
	});
	const shared_dates = dates.filter((date, index) =>
		datasets.every((dataset) => dataset.values[index] !== null)
	);

	return { dates, date_index, datasets, shared_dates };
}

function make_frappe_chart_options(model) {
	const dates = model.shared_dates;
	const datasets = model.datasets.map((dataset) => ({
		...dataset,
		values: dates.map((date) => dataset.values[model.date_index.get(date)]),
	}));
	if (!dates.length || !datasets.length) {
		return;
	}

	return {
		title: "Future XIRR (%) by Year",
		data: {
			labels: dates.map((date) => date.slice(0, 4)),
			datasets,
		},
		type: "line",
		colors: datasets.map((dataset) => dataset.color),
		fieldtype: "Percent",
		height: 360,
		showLegend: 0,
		lineOptions: { hideDots: 1, heatline: 0 },
		axisOptions: {
			shortenYAxisNumbers: 1,
			xAxisMode: "tick",
			xIsSeries: 1,
			numberFormatter: (value) => `${Number(value).toFixed(1)}%`,
		},
		tooltipOptions: {
			formatTooltipX: (value) => String(value),
			formatTooltipY: (value) => `${Number(value).toFixed(2)}%`,
		},
	};
}

function initialize_selected_bonds(report, model) {
	const available = new Set(model.datasets.map((dataset) => dataset.isin));
	if (!report._bond_yield_selected_isins) {
		report._bond_yield_selected_isins = new Set(available);
		return;
	}
	report._bond_yield_selected_isins = new Set(
		[...report._bond_yield_selected_isins].filter((isin) => available.has(isin))
	);
}

function get_selected_chart_model(report, model) {
	const selected = report._bond_yield_selected_isins || new Set();
	const datasets = model.datasets.filter((dataset) => selected.has(dataset.isin));
	const shared_dates = model.dates.filter(
		(date, index) =>
			datasets.length && datasets.every((dataset) => dataset.values[index] !== null)
	);
	return { ...model, datasets, shared_dates };
}

function render_bond_yield_chart(report, model) {
	const selected_model = get_selected_chart_model(report, model);
	if (selected_model.datasets.length) {
		render_gap_aware_chart(report, selected_model);
	} else {
		report.chart_options = null;
		show_no_chart_message(
			report,
			"Select one or more bonds to display their stored Future XIRR."
		);
	}
}

function render_gap_aware_chart(report, model) {
	const chart = {
		title: "Future XIRR (%) by Year",
		data: {
			labels: model.dates.map((date) => date.slice(0, 4)),
			datasets: model.datasets,
		},
		type: "line",
		colors: model.datasets.map((dataset) => dataset.color),
	};
	report.chart_options = null;
	report.chart = chart;
	const geometry = get_gap_chart_geometry(model);
	report.$chart.empty().html(make_gap_chart_svg(model, geometry)).show();
	bind_chart_hover(report, model, geometry);
}

function render_bond_selector(report, model) {
	const selected = report._bond_yield_selected_isins || new Set();
	const $section = $(`<section class="bond-yield-selection" data-bond-yield-selection>
		<div class="flex justify-between align-center mb-2">
			<div class="flex align-center">
				<label class="mb-0">
					<input type="checkbox" class="bond-yield-select-all" data-bond-yield-select-all aria-label="Select all bonds">
					<span class="ml-1">Select all bonds</span>
				</label>
				<h4 class="mb-0 ml-3">Bonds to compare</h4>
			</div>
			<span class="text-muted bond-yield-selection-summary"></span>
		</div>
		<div class="table-responsive">
			<table class="table table-bordered table-hover mb-0">
				<thead><tr><th scope="col">Select</th><th scope="col">Bond ISIN</th><th scope="col">Currency</th></tr></thead>
				<tbody></tbody>
			</table>
		</div>
	</section>`);
	const $body = $section.find("tbody");
	$section.find("[data-bond-yield-select-all]").on("change", (event) => {
		report._bond_yield_selected_isins = event.currentTarget.checked
			? new Set(model.datasets.map((dataset) => dataset.isin))
			: new Set();
		render_bond_yield_chart(report, model);
		sync_bond_selector(report);
	});
	model.datasets.forEach((dataset) => {
		const checkbox = document.createElement("input");
		checkbox.type = "checkbox";
		checkbox.className = "bond-yield-checkbox";
		checkbox.checked = selected.has(dataset.isin);
		checkbox.dataset.bondYieldIsin = dataset.isin;
		checkbox.setAttribute("aria-label", `Select ${dataset.isin}`);
		checkbox.addEventListener("change", () => {
			if (checkbox.checked) {
				report._bond_yield_selected_isins.add(dataset.isin);
			} else {
				report._bond_yield_selected_isins.delete(dataset.isin);
			}
			render_bond_yield_chart(report, model);
			sync_bond_selector(report);
		});

		const checkbox_cell = $("<td class='text-center'>");
		checkbox_cell.append(checkbox);
		const bond_cell = $("<td>");
		const color = $(`<span class="bond-yield-color-dot" aria-hidden="true"></span>`);
		color.css({
			backgroundColor: dataset.color,
			borderRadius: "50%",
			display: "inline-block",
			height: "10px",
			marginRight: "6px",
			width: "10px",
		});
		bond_cell.append(color, document.createTextNode(dataset.isin));
		$body.append(
			$("<tr>").append(checkbox_cell, bond_cell, $("<td>").text(dataset.currency || "—"))
		);
	});

	report._bond_yield_selector = $section;
	report.$chart.after($section);
	update_bond_selector_summary(report);
}

function update_bond_selector_summary(report) {
	const $section = report._bond_yield_selector;
	if (!$section?.length) {
		return;
	}
	const total = $section.find(".bond-yield-checkbox").length;
	const selected = $section.find(".bond-yield-checkbox:checked").length;
	$section.find(".bond-yield-selection-summary").text(`${selected} of ${total} bonds selected`);
	const select_all = $section.find("[data-bond-yield-select-all]")[0];
	if (select_all) {
		select_all.checked = total > 0 && selected === total;
		select_all.indeterminate = selected > 0 && selected < total;
	}
}

function sync_bond_selector(report) {
	const selected = report._bond_yield_selected_isins || new Set();
	report._bond_yield_selector?.find(".bond-yield-checkbox").each((_, checkbox) => {
		checkbox.checked = selected.has(checkbox.dataset.bondYieldIsin);
	});
	update_bond_selector_summary(report);
}

function render_audit_copy_button(report) {
	const $audit = $(`<section class="bond-yield-audit mt-3" data-bond-yield-audit>
		<button type="button" class="btn btn-secondary btn-sm" data-copy-audit-data>Copy audit data to Excel</button>
		<span class="text-muted ml-2">Copies the report rows, including market price and stored Future XIRR.</span>
	</section>`);
	$audit.find("[data-copy-audit-data]").on("click", () => copy_audit_data(report));
	report._bond_yield_audit = $audit;
	report._bond_yield_selector.after($audit);
}

function copy_audit_data(report) {
	const columns = (report.raw_data?.columns || []).filter((column) => !column.hidden);
	const rows = report.raw_data?.result || [];
	const lines = [
		columns.map((column) => audit_cell(column.label)).join("\t"),
		...rows.map((row) =>
			columns.map((column) => audit_cell(row[column.fieldname])).join("\t")
		),
	];
	frappe.utils.copy_to_clipboard(
		lines.join("\n"),
		"Audit data copied to clipboard. You can paste it into Excel."
	);
}

function audit_cell(value) {
	return String(value ?? "").replace(/[\t\r\n]+/g, " ");
}

function remove_report_controls(report) {
	report._bond_yield_selector?.remove();
	report._bond_yield_audit?.remove();
	report._bond_yield_selector = null;
	report._bond_yield_audit = null;
}

function show_no_chart_message(report, message) {
	report.chart = null;
	report.$chart.html(`<div class="text-muted text-center py-4">${message}</div>`).show();
}

function get_gap_chart_geometry(model) {
	const values = model.datasets.flatMap((dataset) =>
		dataset.values.filter((value) => value !== null)
	);
	const min = Math.min(...values);
	const max = Math.max(...values);
	const span = max - min;
	const padding = span ? Math.max(span * 0.1, 0.5) : Math.max(Math.abs(max) * 0.1, 1);
	const range = { min: min - padding, max: max + padding };
	const plot_width = GAP_CHART_LAYOUT.width - GAP_CHART_LAYOUT.left - GAP_CHART_LAYOUT.right;
	const plot_height = GAP_CHART_LAYOUT.bottom - GAP_CHART_LAYOUT.top;
	const x = (index) =>
		model.dates.length === 1
			? GAP_CHART_LAYOUT.left + plot_width / 2
			: GAP_CHART_LAYOUT.left + (index / (model.dates.length - 1)) * plot_width;
	const y = (value) =>
		GAP_CHART_LAYOUT.top + ((range.max - value) / (range.max - range.min)) * plot_height;
	return {
		...GAP_CHART_LAYOUT,
		plot_width,
		plot_height,
		height: GAP_CHART_LAYOUT.bottom + 60,
		range,
		x,
		y,
	};
}

function make_gap_chart_svg(model, geometry = get_gap_chart_geometry(model)) {
	const { width, left, top, bottom, height, plot_width, range, x, y } = geometry;
	const parts = [
		`<svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="Future XIRR comparison chart" data-chart-mode="gap-aware">`,
		`<text x="${
			width / 2
		}" y="20" text-anchor="middle" class="chart-title">Future XIRR (%) by Year</text>`,
		`<text x="18" y="${(top + bottom) / 2}" transform="rotate(-90 18 ${
			(top + bottom) / 2
		})" text-anchor="middle" class="chart-axis-title">Future XIRR (%)</text>`,
		`<text x="${left + plot_width / 2}" y="${
			bottom + 48
		}" text-anchor="middle" class="chart-axis-title">Market date (year)</text>`,
	];

	for (let index = 0; index < 5; index += 1) {
		const value = range.max - ((range.max - range.min) * index) / 4;
		const position = y(value);
		parts.push(
			`<line x1="${left}" x2="${
				left + plot_width
			}" y1="${position}" y2="${position}" class="chart-grid-line"/>`,
			`<text x="${left - 10}" y="${
				position + 4
			}" text-anchor="end" class="chart-axis-label">${format_percent(value, 1)}</text>`
		);
	}
	parts.push(
		`<line x1="${left}" x2="${left}" y1="${top}" y2="${bottom}" class="chart-axis-line"/>`,
		`<line x1="${left}" x2="${
			left + plot_width
		}" y1="${bottom}" y2="${bottom}" class="chart-axis-line"/>`
	);

	const year_positions = new Map();
	model.dates.forEach((date, index) => {
		const year = date.slice(0, 4);
		if (!year_positions.has(year)) {
			year_positions.set(year, x(index));
		}
	});
	year_positions.forEach((x, year) => {
		parts.push(
			`<text x="${x}" y="${
				bottom + 18
			}" text-anchor="middle" class="chart-axis-label">${year}</text>`
		);
	});

	model.datasets.forEach((dataset, dataset_index) => {
		let segment = [];
		dataset.values.forEach((value, index) => {
			if (value === null) {
				return;
			}

			const point = { x: x(index), y: y(value), index, value };
			segment.push(point);
		});
		append_data_line(parts, segment, dataset.color, dataset.name, dataset_index);
	});

	parts.push("</svg>");
	return parts.join("");
}

function append_data_line(parts, points, color, name, dataset_index) {
	if (points.length < 2) {
		return;
	}
	const path = points
		.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`)
		.join(" ");
	parts.push(
		`<path d="${path}" fill="none" stroke="${color}" stroke-width="2" pointer-events="stroke" class="chart-data-line" data-bond-yield-dataset="${dataset_index}"><title>${escape_svg(
			name
		)}</title></path>`
	);
}

function bind_chart_hover(report, model, geometry) {
	const $chart = report.$chart;
	const svg = $chart.find('svg[data-chart-mode="gap-aware"]')[0];
	if (!svg) {
		return;
	}

	$chart.css("position", "relative");
	const tooltip = document.createElement("div");
	tooltip.className = "bond-yield-hover-tooltip";
	tooltip.dataset.bondYieldHoverTooltip = "true";
	tooltip.style.cssText =
		"display:none;position:absolute;z-index:10;pointer-events:none;padding:6px 8px;border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);box-shadow:var(--card-shadow);font-size:12px;";
	tooltip.innerHTML =
		"<strong data-bond-yield-hover-isin></strong><br><span data-bond-yield-hover-value></span>";
	$chart[0].appendChild(tooltip);

	$chart.find(".chart-data-line").each((_, line) => {
		line.addEventListener("mousemove", (event) => {
			const dataset = model.datasets[Number(line.dataset.bondYieldDataset)];
			const value = get_hover_line_value(dataset, event, svg, geometry);
			if (!dataset || value === null) {
				tooltip.style.display = "none";
				return;
			}

			tooltip.querySelector("[data-bond-yield-hover-isin]").textContent = dataset.isin;
			tooltip.querySelector(
				"[data-bond-yield-hover-value]"
			).textContent = `Future XIRR: ${format_percent(value, 2)}`;
			position_chart_tooltip(tooltip, event, $chart[0]);
		});
		line.addEventListener("mouseleave", () => {
			tooltip.style.display = "none";
		});
	});
}

function get_hover_line_value(dataset, event, svg, geometry) {
	if (!dataset) {
		return null;
	}
	const rect = svg.getBoundingClientRect();
	if (!rect.width || !rect.height) {
		return null;
	}
	const pointer_x = ((event.clientX - rect.left) / rect.width) * geometry.width;
	const pointer_y = ((event.clientY - rect.top) / rect.height) * geometry.height;
	const points = dataset.values
		.map((value, index) =>
			value === null ? null : { x: geometry.x(index), y: geometry.y(value), value }
		)
		.filter(Boolean);
	if (!points.length) {
		return null;
	}

	let closest = null;
	for (let index = 0; index < points.length - 1; index += 1) {
		const start = points[index];
		const end = points[index + 1];
		const horizontal_span = end.x - start.x;
		const ratio = horizontal_span ? (pointer_x - start.x) / horizontal_span : 0;
		const bounded_ratio = Math.max(0, Math.min(1, ratio));
		const line_y = start.y + (end.y - start.y) * bounded_ratio;
		const distance = Math.abs(pointer_y - line_y);
		if (!closest || distance < closest.distance) {
			closest = {
				distance,
				value: start.value + (end.value - start.value) * bounded_ratio,
			};
		}
	}

	if (!closest) {
		const nearest = points.reduce((result, point) =>
			Math.abs(pointer_x - point.x) < Math.abs(pointer_x - result.x) ? point : result
		);
		return nearest.value;
	}
	return closest.value;
}

function position_chart_tooltip(tooltip, event, chart) {
	tooltip.style.display = "block";
	const chart_rect = chart.getBoundingClientRect();
	const tooltip_width = tooltip.offsetWidth;
	const tooltip_height = tooltip.offsetHeight;
	const max_left = Math.max(chart_rect.width - tooltip_width - 4, 4);
	const max_top = Math.max(chart_rect.height - tooltip_height - 4, 4);
	const left = Math.min(Math.max(event.clientX - chart_rect.left + 12, 4), max_left);
	const top = Math.min(
		Math.max(event.clientY - chart_rect.top - tooltip_height - 12, 4),
		max_top
	);
	tooltip.style.left = `${left}px`;
	tooltip.style.top = `${top}px`;
}

function format_percent(value, decimals) {
	return `${Number(value).toFixed(decimals)}%`;
}

function escape_svg(value) {
	return String(value).replace(/[&<>"']/g, (character) => {
		const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
		return entities[character];
	});
}

function date_key(value) {
	return value ? String(value).slice(0, 10) : null;
}

function parse_xirr(value) {
	if (value === null || value === undefined) {
		return null;
	}
	if (typeof value === "string") {
		value = value.trim();
		if (!value) {
			return null;
		}
	} else if (typeof value !== "number") {
		return null;
	}

	const number = Number(value);
	return Number.isFinite(number) ? number : null;
}

function create_currency_colors(currency_by_bond) {
	const currencies = [...new Set(currency_by_bond.values())].sort();
	return new Map(currencies.map((currency) => [currency, get_currency_color(currency)]));
}

function get_currency_color(currency) {
	const code = String(currency || "").toUpperCase();
	if (CURRENCY_COLORS_BY_CODE[code]) {
		return CURRENCY_COLORS_BY_CODE[code];
	}

	const hash = [...code].reduce(
		(value, character) => (value * 31 + character.charCodeAt(0)) >>> 0,
		0
	);
	return FALLBACK_CURRENCY_COLORS[hash % FALLBACK_CURRENCY_COLORS.length];
}
