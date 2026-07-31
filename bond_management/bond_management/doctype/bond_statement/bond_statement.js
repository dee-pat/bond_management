// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bond Statement", {
	attachment(frm) {
		if (!frm.doc.attachment) {
			return Promise.all([
				frm.set_value("portfolio_name", null),
				frm.set_value("statement_date", null),
			]);
		}

		return frm
			.call("read_statement_pdf")
			.then(({ message }) =>
				Promise.all([
					frm.set_value("portfolio_name", message.portfolio_name),
					frm.set_value("statement_date", message.statement_date),
				])
			)
			.then(() => {
				frappe.show_alert({
					message: __("Portfolio and statement date read from PDF"),
					indicator: "green",
				});
			});
	},
});
