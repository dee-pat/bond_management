// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

// Desk keeps the audit table; the investor app draws the only yield chart.
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

	onload(report) {
		report.page.add_inner_button(__("Open chart"), () => {
			window.location.assign("/bond-investor/yield-comparison");
		});
	},
};
