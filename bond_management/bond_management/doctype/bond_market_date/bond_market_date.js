// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const market_recalculation_method =
	"bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_recalculated_market_data";
const market_cashflow_method =
	"bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_cashflows";
const market_recalculation_state = new WeakMap();

frappe.ui.form.on("Bond Market Date", {
	refresh(frm) {
		render_yield_curve(frm);
	},
	date: schedule_market_recalculation,
});

frappe.ui.form.on("Bond Market Prices", {
	market_price: schedule_market_recalculation,
	isin: schedule_market_recalculation,
	bond_market_prices_add: schedule_market_recalculation,
	bond_market_prices_remove: schedule_market_recalculation,
	copy_cashflows(frm, cdt, cdn) {
		return copy_cashflows(frm, locals[cdt][cdn]);
	},
});

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
			date: frm.doc.date,
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
	const derived_fields = ["currency", "future_xirr", "principal_factor", "maturity_date"];
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

			return copy_to_clipboard(tsv).then(() => {
				frappe.show_alert({
					message: __("Copied cash flows for {0}", [isin]),
					indicator: "green",
				});
				return cashflows;
			});
		});
}

function copy_to_clipboard(text) {
	if (navigator.clipboard && window.isSecureContext) {
		return navigator.clipboard.writeText(text).catch(() => fallback_copy(text));
	}

	return fallback_copy(text);
}

function fallback_copy(text) {
	return new Promise((resolve, reject) => {
		const textarea = document.createElement("textarea");
		textarea.value = text;
		textarea.style.position = "fixed";
		textarea.style.opacity = "0";
		document.body.appendChild(textarea);
		textarea.select();

		try {
			if (!document.execCommand("copy")) {
				throw new Error("The browser did not copy the cash flows.");
			}
			resolve();
		} catch (error) {
			reject(error);
		} finally {
			textarea.remove();
		}
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
	const svg = append_svg(container, "svg", {
		viewBox: `0 0 ${width} ${height}`,
		role: "img",
		"aria-label": __("Yield curve with numeric year spacing"),
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

	data.forEach((point) => {
		const circle = append_svg(svg, "circle", {
			cx: x_position(point.years),
			cy: y_position(point.yield_percent),
			r: 5,
			fill: "#3366ff",
			stroke: "#ffffff",
			"stroke-width": 1.5,
			tabindex: 0,
			"aria-label": format_yield_tooltip(point),
		});
		append_svg(circle, "title", {}, format_yield_tooltip(point));
	});

	wrapper.append(container);
}

function get_yield_curve_data(frm) {
	if (!frm.doc.date) {
		return [];
	}

	return (frm.doc.bond_market_prices || [])
		.map((row) => {
			const repayment_date = row.maturity_date;
			const years = repayment_date
				? frappe.datetime.get_day_diff(repayment_date, frm.doc.date) / 365
				: NaN;
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
		__("Years to repayment")
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
	return __("{0} | {1} | {2} years | Yield {3}%", [
		point.isin,
		point.repayment_date,
		point.years.toFixed(2),
		point.yield_percent.toFixed(4),
	]);
}
