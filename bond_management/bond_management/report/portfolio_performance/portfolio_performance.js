// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

frappe.query_reports["Portfolio Performance"] = {
	filters: [
    	{
            fieldname: "portfolio",
            label: "Portfolio",
            fieldtype: "Link",
            options: "Bond Portfolio",
            reqd: 1
        },
        {
            fieldname: "valuation_date",
            label: "Valuation Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        }
	],
};
