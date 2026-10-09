// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

frappe.query_reports["Interest Difference by Portfolio"] = {
	filters: [
		{
			fieldname: "portfolio_name",
			label: __("Portfolio"),
			fieldtype: "Link",
			options: "Bond Portfolio",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
	],
};
