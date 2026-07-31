// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bond Statement", {
	refresh(frm) {
		make_statement_attachment_filename_readable(frm);
	},
	attachment(frm) {
		make_statement_attachment_filename_readable(frm);
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

function make_statement_attachment_filename_readable(frm) {
	const attachment = frm.get_field("attachment");
	attachment?.$value?.css({
		"min-height": "56px",
		padding: "8px 10px",
		gap: "8px",
		"align-items": "flex-start",
	});
	attachment?.$value?.find(".ellipsis, .attached-file-link").css({
		"white-space": "normal",
		overflow: "visible",
		"text-overflow": "clip",
		"overflow-wrap": "anywhere",
		"line-height": "1.35",
	});
}
