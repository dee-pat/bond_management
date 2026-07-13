// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

frappe.query_reports["Portfolio Performance"] = {
	filters: [
		{
			fieldname: "portfolio",
			label: "Portfolio",
			fieldtype: "Link",
			options: "Bond Portfolio",
			reqd: 1,
		},
		{
			fieldname: "valuation_date",
			label: "Valuation Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted_value = default_formatter(value, row, column, data);
		if (!data || !["xirr", "future_xirr"].includes(column.fieldname)) {
			return formatted_value;
		}

		return `<button class="btn btn-link btn-xs portfolio-cashflow-copy" data-isin="${frappe.utils.escape_html(
			data.isin
		)}" data-xirr-type="${
			column.fieldname === "xirr" ? "past" : "future"
		}" title="Copy cash flows for Excel">${formatted_value}</button>`;
	},
	onload(report) {
		const selector = ".portfolio-cashflow-copy";
		report.page.wrapper.off("click.portfolio-cashflow", selector);
		report.page.wrapper.on("click.portfolio-cashflow", selector, (event) => {
			event.preventDefault();
			event.stopPropagation();
			const button = $(event.currentTarget);
			return copy_xirr_cashflows(
				report,
				button.attr("data-isin"),
				button.attr("data-xirr-type")
			).catch(frappe.msgprint);
		});
	},
};

function copy_xirr_cashflows(report, isin, xirr_type) {
	const filters = report.get_values();
	return frappe
		.call({
			method: "bond_management.bond_management.report.portfolio_performance.portfolio_performance.get_xirr_cashflows",
			type: "POST",
			args: {
				portfolio: filters.portfolio,
				valuation_date: filters.valuation_date,
				isin,
				xirr_type,
			},
		})
		.then((response) => {
			const cashflows = response.message || [];
			if (!cashflows.length) {
				frappe.show_alert({ message: "No cash flows found", indicator: "orange" });
				return cashflows;
			}

			const tsv = [
				"isin\ttransaction_type\tdate\tamount",
				...cashflows.map(
					(flow) =>
						`${flow.isin}\t${flow.transaction_type}\t${flow.date}\t${flow.amount}`
				),
			].join("\n");
			frappe.utils.copy_to_clipboard(tsv, `Copied ${cashflows.length} cash flows`);
			return cashflows;
		});
}
