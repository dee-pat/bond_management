// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const market_recalculation_method =
	"bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_recalculated_market_data";
const market_cashflow_method =
	"bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_cashflows";
const market_recalculation_state = new WeakMap();
const cashflow_copy_bindings = new WeakMap();

frappe.ui.form.on("Bond Market Date", {
	setup(frm) {
		set_future_xirr_formatter(frm);
	},
	refresh(frm) {
		set_future_xirr_formatter(frm);
		bind_cashflow_copy(frm);
		render_yield_curve(frm);
	},
	date: schedule_market_recalculation,
});

frappe.ui.form.on("Bond Market Prices", {
	market_price: schedule_market_recalculation,
	isin: schedule_market_recalculation,
	bond_market_prices_add: schedule_market_recalculation,
	bond_market_prices_remove: schedule_market_recalculation,
});

function set_future_xirr_formatter(frm) {
	const formatter = (value, df, options, row) => {
		const formatted_value = frappe.form.formatters.Percent(
			value,
			df,
			{ ...(options || {}), inline: true },
			row
		);
		if (value === null || value === undefined || !row || !row.name || !row.isin) {
			return formatted_value;
		}

		const copy_label = __("Copy cash flows for {0}", [row.isin]);
		return `<button type="button" class="btn btn-link btn-xs bond-market-cashflow-copy" data-row-name="${frappe.utils.escape_html(
			row.name
		)}" data-isin="${frappe.utils.escape_html(
			row.isin
		)}" aria-label="${frappe.utils.escape_html(copy_label)}" title="${frappe.utils.escape_html(
			__("Copy cash flows for Excel")
		)}">${formatted_value}</button>`;
	};

	const standard_field = frappe.meta.docfield_map["Bond Market Prices"]?.future_xirr;
	if (standard_field) {
		standard_field.formatter = formatter;
	}

	const document_field = frappe.meta.get_docfield(
		"Bond Market Prices",
		"future_xirr",
		frm.docname
	);
	if (document_field) {
		document_field.formatter = formatter;
	}
}

function bind_cashflow_copy(frm) {
	const grid = frm.fields_dict.bond_market_prices?.grid;
	if (!grid) {
		return;
	}

	const selector = ".bond-market-cashflow-copy";
	const wrapper = grid.wrapper.get(0);
	const previous_binding = cashflow_copy_bindings.get(frm);
	if (previous_binding?.wrapper === wrapper) {
		return;
	}
	if (previous_binding) {
		previous_binding.wrapper.removeEventListener("click", previous_binding.handler, true);
	}

	const handler = (event) => {
		const button = event.target.closest?.(selector);
		if (!button || !wrapper.contains(button)) {
			return;
		}

		// Frappe's grid cell click handler runs in the bubble phase and would open
		// the editable row before a delegated jQuery handler could stop it.
		event.preventDefault();
		event.stopPropagation();

		const row_name = button.dataset.rowName;
		const row = (frm.doc.bond_market_prices || []).find(
			(market_price) => market_price.name === row_name
		);
		copy_cashflows(frm, row).catch(frappe.msgprint);
	};

	wrapper.addEventListener("click", handler, true);
	cashflow_copy_bindings.set(frm, { wrapper, handler });
}

function get_market_state(frm) {
	if (!market_recalculation_state.has(frm)) {
		market_recalculation_state.set(frm, {
			request_id: 0,
			timer: null,
			waiters: [],
		});
	}

	return market_recalculation_state.get(frm);
}

function schedule_market_recalculation(frm) {
	const state = get_market_state(frm);
	const request_id = ++state.request_id;

	if (state.timer) {
		clearTimeout(state.timer);
	}

	const pending = new Promise((resolve, reject) => {
		state.waiters.push({ resolve, reject });
	});

	state.timer = setTimeout(() => {
		state.timer = null;
		const waiters = state.waiters.splice(0);
		const calculation = recalculate_market_data(frm, state, request_id);
		calculation.then(
			(result) => waiters.forEach(({ resolve }) => resolve(result)),
			(error) => waiters.forEach(({ reject }) => reject(error))
		);
	}, 350);

	return pending;
}

async function recalculate_market_data(frm, state, request_id) {
	const rows = (frm.doc.bond_market_prices || []).map((row) => ({
		name: row.name,
		isin: row.isin,
		market_price: row.market_price,
	}));

	if (!rows.length) {
		if (request_id === state.request_id) {
			render_yield_curve(frm);
		}
		return [];
	}

	const response = await frappe.call({
		method: market_recalculation_method,
		type: "POST",
		args: {
			// Frappe omits undefined request arguments. Send an empty value so
			// rows can be populated before the parent market date is entered.
			date: frm.doc.date || "",
			rows: JSON.stringify(rows),
		},
	});

	if (request_id !== state.request_id) {
		return response.message;
	}

	await apply_market_calculation(frm, response.message || []);
	if (request_id === state.request_id) {
		frm.refresh_field("bond_market_prices");
		render_yield_curve(frm);
	}

	return response.message;
}

function apply_market_calculation(frm, calculated_rows) {
	const calculations_by_name = new Map(
		calculated_rows.filter((row) => row.name).map((row) => [row.name, row])
	);
	const derived_fields = [
		"currency",
		"future_xirr",
		"principal_factor",
		"weighted_avg_repayment_date",
		"weighted_avg_repayment_years",
		"maturity_date",
	];
	const updates = (frm.doc.bond_market_prices || []).flatMap((row) => {
		const calculated = calculations_by_name.get(row.name) || {};
		return derived_fields.map((fieldname) =>
			frappe.model.set_value(row.doctype, row.name, fieldname, calculated[fieldname] ?? null)
		);
	});

	return Promise.all(updates);
}

function copy_cashflows(frm, row) {
	if (!frm.doc.date) {
		frappe.msgprint(__("Enter the market date before copying cash flows."));
		return Promise.resolve([]);
	}
	if (!row || !row.isin) {
		frappe.msgprint(__("Select an ISIN before copying cash flows."));
		return Promise.resolve([]);
	}
	if (row.market_price === null || row.market_price === undefined) {
		frappe.msgprint(__("Enter a market price before copying cash flows."));
		return Promise.resolve([]);
	}
	if (Number(row.market_price) <= 0) {
		frappe.msgprint(__("Market Price must be greater than zero."));
		return Promise.resolve([]);
	}

	const isin = row.isin;
	return frappe
		.call({
			method: market_cashflow_method,
			type: "POST",
			args: {
				date: frm.doc.date,
				isin,
				market_price: row.market_price,
			},
		})
		.then((response) => {
			const cashflows = response.message || [];
			if (!cashflows.length) {
				frappe.msgprint(__("No cash flows found."));
				return cashflows;
			}

			cashflows.sort((left, right) => left.date.localeCompare(right.date));
			const tsv = [
				"isin\ttransaction_type\tdate\tamount",
				...cashflows.map(
					(flow) => `${flow.isin}\t${flow.type}\t${flow.date}\t${flow.amount}`
				),
			].join("\n");

			frappe.utils.copy_to_clipboard(
				tsv,
				__("Copied {0} cash flows for {1}", [cashflows.length, isin])
			);
			return cashflows;
		});
}

function render_yield_curve(frm) {
	const field = frm.fields_dict.yield_curve_chart;
	if (!field) {
		return;
	}

	const wrapper = field.$wrapper;
	wrapper.empty();
	const data = get_yield_curve_data(frm);
	if (!data.length) {
		wrapper.text(__("No valid yield-curve data."));
		return;
	}

	const width = 900;
	const height = 340;
	const margin = { top: 35, right: 25, bottom: 58, left: 72 };
	const plot_width = width - margin.left - margin.right;
	const plot_height = height - margin.top - margin.bottom;
	const x_max = Math.max(...data.map((point) => point.years));
	const yields = data.map((point) => point.yield_percent);
	let y_min = Math.min(...yields);
	let y_max = Math.max(...yields);
	const y_padding =
		y_min === y_max
			? Math.max(Math.abs(y_min) * 0.1, 1)
			: Math.max((y_max - y_min) * 0.1, 0.25);
	y_min -= y_padding;
	y_max += y_padding;

	const x_position = (years) => margin.left + (years / x_max) * plot_width;
	const y_position = (yield_percent) =>
		margin.top + ((y_max - yield_percent) / (y_max - y_min)) * plot_height;

	const container = document.createElement("div");
	container.className = "bond-yield-curve";
	container.style.position = "relative";
	const svg = append_svg(container, "svg", {
		viewBox: `0 0 ${width} ${height}`,
		role: "img",
		"aria-label": __("Yield curve by weighted average principal repayment"),
		style: "display:block;width:100%;height:auto;max-height:340px",
	});
	append_svg(svg, "title", {}, __("Yield Curve"));
	append_svg(
		svg,
		"text",
		{
			x: width / 2,
			y: 20,
			"text-anchor": "middle",
			"font-size": 15,
			"font-weight": 600,
			fill: "currentColor",
		},
		__("Yield Curve")
	);

	draw_yield_axes(
		svg,
		{ width, height, margin, plot_width, plot_height, x_max, y_min, y_max },
		x_position,
		y_position
	);

	const line_points = data
		.map((point) => `${x_position(point.years)},${y_position(point.yield_percent)}`)
		.join(" ");
	append_svg(svg, "polyline", {
		points: line_points,
		fill: "none",
		stroke: "#3366ff",
		"stroke-width": 2.5,
		"stroke-linejoin": "round",
		"stroke-linecap": "round",
	});

	const tooltip = document.createElement("div");
	tooltip.className = "bond-yield-tooltip";
	tooltip.setAttribute("role", "tooltip");
	tooltip.hidden = true;
	Object.assign(tooltip.style, {
		position: "absolute",
		zIndex: "1",
		maxWidth: "min(420px, calc(100% - 16px))",
		padding: "6px 9px",
		borderRadius: "var(--border-radius-md)",
		background: "var(--gray-900)",
		color: "var(--gray-50)",
		fontSize: "12px",
		lineHeight: "1.4",
		textAlign: "center",
		pointerEvents: "none",
		transform: "translate(-50%, calc(-100% - 10px))",
	});
	container.appendChild(tooltip);

	data.forEach((point) => {
		const tooltip_text = format_yield_tooltip(point);
		const circle = append_svg(svg, "circle", {
			cx: x_position(point.years),
			cy: y_position(point.yield_percent),
			r: 7,
			fill: "#3366ff",
			stroke: "#ffffff",
			"stroke-width": 1.5,
			tabindex: 0,
			class: "bond-yield-point",
			"data-isin": point.isin,
			"data-repayment-date": point.repayment_date,
			"aria-label": tooltip_text,
		});
		append_svg(circle, "title", {}, tooltip_text);

		const show_tooltip = () => {
			const svg_bounds = svg.getBoundingClientRect();
			const container_bounds = container.getBoundingClientRect();
			const scale_x = svg_bounds.width / width;
			const scale_y = svg_bounds.height / height;
			tooltip.textContent = tooltip_text;
			tooltip.style.left = `${
				svg_bounds.left -
				container_bounds.left +
				Number(circle.getAttribute("cx")) * scale_x
			}px`;
			tooltip.style.top = `${
				svg_bounds.top - container_bounds.top + Number(circle.getAttribute("cy")) * scale_y
			}px`;
			tooltip.hidden = false;
		};
		const hide_tooltip = () => {
			tooltip.hidden = true;
		};

		circle.addEventListener("mouseenter", show_tooltip);
		circle.addEventListener("mouseleave", hide_tooltip);
		circle.addEventListener("focus", show_tooltip);
		circle.addEventListener("blur", hide_tooltip);
	});

	wrapper.append(container);
}

function get_yield_curve_data(frm) {
	if (!frm.doc.date) {
		return [];
	}

	return (frm.doc.bond_market_prices || [])
		.map((row) => {
			const repayment_date = row.weighted_avg_repayment_date;
			const years =
				row.weighted_avg_repayment_years === null ||
				row.weighted_avg_repayment_years === undefined
					? NaN
					: Number(row.weighted_avg_repayment_years);
			return {
				isin: row.isin,
				repayment_date,
				years,
				yield_percent:
					row.future_xirr === null || row.future_xirr === undefined
						? NaN
						: Number(row.future_xirr),
			};
		})
		.filter(
			(point) =>
				point.isin &&
				point.repayment_date &&
				point.years > 0 &&
				Number.isFinite(point.years) &&
				Number.isFinite(point.yield_percent)
		)
		.sort((left, right) => left.years - right.years);
}

function draw_yield_axes(svg, dimensions, x_position, y_position) {
	const { height, margin, plot_width, plot_height, x_max, y_min, y_max } = dimensions;
	const tick_count = 5;

	for (let index = 0; index < tick_count; index += 1) {
		const ratio = index / (tick_count - 1);
		const x_value = x_max * ratio;
		const x = x_position(x_value);
		const y_value = y_max - (y_max - y_min) * ratio;
		const y = y_position(y_value);

		append_svg(svg, "line", {
			x1: margin.left,
			y1: y,
			x2: margin.left + plot_width,
			y2: y,
			stroke: "#dfe2e5",
			"stroke-width": 1,
		});
		append_svg(
			svg,
			"text",
			{
				x: margin.left - 10,
				y: y + 4,
				"text-anchor": "end",
				"font-size": 11,
				fill: "currentColor",
			},
			`${y_value.toFixed(2)}%`
		);
		append_svg(svg, "line", {
			x1: x,
			y1: margin.top + plot_height,
			x2: x,
			y2: margin.top + plot_height + 5,
			stroke: "currentColor",
		});
		append_svg(
			svg,
			"text",
			{
				x,
				y: margin.top + plot_height + 20,
				"text-anchor": "middle",
				"font-size": 11,
				fill: "currentColor",
			},
			format_years(x_value)
		);
	}

	append_svg(svg, "line", {
		x1: margin.left,
		y1: margin.top,
		x2: margin.left,
		y2: margin.top + plot_height,
		stroke: "currentColor",
	});
	append_svg(svg, "line", {
		x1: margin.left,
		y1: margin.top + plot_height,
		x2: margin.left + plot_width,
		y2: margin.top + plot_height,
		stroke: "currentColor",
	});
	append_svg(
		svg,
		"text",
		{
			x: margin.left + plot_width / 2,
			y: height - 8,
			"text-anchor": "middle",
			"font-size": 12,
			fill: "currentColor",
		},
		__("Years to weighted average principal repayment")
	);
	append_svg(
		svg,
		"text",
		{
			x: 16,
			y: margin.top + plot_height / 2,
			transform: `rotate(-90 16 ${margin.top + plot_height / 2})`,
			"text-anchor": "middle",
			"font-size": 12,
			fill: "currentColor",
		},
		__("Yield (%)")
	);
}

function append_svg(parent, tag_name, attributes, text) {
	const element = document.createElementNS(SVG_NAMESPACE, tag_name);
	Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
	if (text !== undefined) {
		element.textContent = text;
	}
	parent.appendChild(element);
	return element;
}

function format_years(years) {
	return `${years.toFixed(years >= 10 ? 1 : 2)}y`;
}

function format_yield_tooltip(point) {
	return __("ISIN: {0} | Weighted repayment: {1} | {2} years | Yield {3}%", [
		point.isin,
		point.repayment_date,
		point.years.toFixed(2),
		point.yield_percent.toFixed(4),
	]);
}
