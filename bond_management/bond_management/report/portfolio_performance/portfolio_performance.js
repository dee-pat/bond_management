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
		const cashflow_columns = {
			xirr: { xirr_type: "past", cashflow_currency: "native" },
			future_xirr: { xirr_type: "future", cashflow_currency: "native" },
			xirr_usd: { xirr_type: "past", cashflow_currency: "reporting" },
			future_xirr_usd: { xirr_type: "future", cashflow_currency: "reporting" },
		};
		const cashflow = cashflow_columns[column.fieldname];
		if (
			!data ||
			!cashflow ||
			value === null ||
			value === undefined ||
			(data.isin === "TOTAL" && cashflow.cashflow_currency === "native" && !data.currency)
		) {
			return formatted_value;
		}

		return `<button class="btn btn-link btn-xs portfolio-cashflow-copy" data-isin="${frappe.utils.escape_html(
			data.isin
		)}" data-xirr-type="${cashflow.xirr_type}" data-cashflow-currency="${
			cashflow.cashflow_currency
		}" title="Copy ${
			cashflow.cashflow_currency
		} cash flows for Excel">${formatted_value}</button>`;
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
				button.attr("data-xirr-type"),
				button.attr("data-cashflow-currency")
			).catch(frappe.msgprint);
		});
	},
};

function copy_xirr_cashflows(report, isin, xirr_type, cashflow_currency) {
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
				cashflow_currency,
			},
		})
		.then((response) => {
			const cashflows = response.message || [];
			if (!cashflows.length) {
				frappe.show_alert({ message: "No cash flows found", indicator: "orange" });
				return cashflows;
			}

			const tsv = [
				"isin\ttransaction_type\tdate\tcurrency\tamount\tquantity\trate",
				...cashflows.map(
					(flow) =>
						`${flow.isin}\t${flow.transaction_type}\t${flow.date}\t${flow.currency}\t${flow.amount}\t${flow.quantity}\t${flow.rate}`
				),
			].join("\n");
			frappe.utils.copy_to_clipboard(tsv, `Copied ${cashflows.length} cash flows`);
			return cashflows;
		});
}
