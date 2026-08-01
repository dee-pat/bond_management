// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

const statement_attachment_state = new WeakMap();

frappe.ui.form.on("Bond Statement", {
	refresh(frm) {
		make_statement_attachment_filename_readable(frm);
	},
	attachment(frm) {
		make_statement_attachment_filename_readable(frm);
		const state = get_statement_attachment_state(frm);
		const request_id = ++state.request_id;
		if (!frm.doc.attachment) {
			if (request_id !== state.request_id) {
				return Promise.resolve();
			}
			return frm.set_value({
				portfolio_name: null,
				statement_date: null,
			});
		}

		return frm.call("read_statement_pdf").then(({ message }) => {
			if (request_id !== state.request_id) {
				return message;
			}
			return frm
				.set_value({
					portfolio_name: message.portfolio_name,
					statement_date: message.statement_date,
				})
				.then(() => {
					if (request_id !== state.request_id) {
						return message;
					}
					frappe.show_alert({
						message: __("Portfolio and statement date read from PDF"),
						indicator: "green",
					});
					return message;
				});
		});
	},
});

function get_statement_attachment_state(frm) {
	if (!statement_attachment_state.has(frm)) {
		statement_attachment_state.set(frm, { request_id: 0 });
	}
	return statement_attachment_state.get(frm);
}

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
