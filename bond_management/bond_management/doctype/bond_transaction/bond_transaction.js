// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

const transaction_calculation_state = new WeakMap();
const transaction_calculation_method =
	"bond_management.bond_management.doctype.bond_transaction.bond_transaction.get_calculated_amounts";
const pdf_managed_fields = [
	"transaction_reference",
	"transaction_type",
	"isin",
	"portfolio_name",
	"trade_date",
	"settlement_date",
	"quantity_face_value",
	"price",
	"accrued_interest_paid",
	"commission",
];

frappe.ui.form.on("Bond Transaction", {
	refresh(frm) {
		make_transaction_attachment_filename_readable(frm);
		set_pdf_fields_read_only(frm, is_pdf_attachment(frm.doc.attachment));
	},
	attachment(frm) {
		make_transaction_attachment_filename_readable(frm);
		if (!frm.doc.attachment) {
			set_pdf_fields_read_only(frm, false);
			return Promise.resolve();
		}
		if (!is_pdf_attachment(frm.doc.attachment)) {
			set_pdf_fields_read_only(frm, false);
			frappe.msgprint(
				__(
					"Automatic transaction entry requires a PDF. Remove this attachment to use manual entry."
				)
			);
			return Promise.resolve();
		}

		return frm.call("read_transaction_pdf").then(({ message }) => {
			const transactions = message?.transactions || [];
			if (transactions.length === 1) {
				return apply_pdf_transaction(frm, transactions[0]);
			}
			return show_transaction_selection(frm, transactions);
		});
	},
	face_value_per_unit: calculate_all,
	quantity_face_value: calculate_all,
	price: calculate_all,
	accrued_interest_paid: calculate_after_accrued_interest_change,
	commission: calculate_all,
	settlement_date: calculate_all,
	isin: calculate_all,
});

function make_transaction_attachment_filename_readable(frm) {
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

function is_pdf_attachment(attachment) {
	return Boolean(attachment && attachment.toLowerCase().endsWith(".pdf"));
}

function set_pdf_fields_read_only(frm, read_only) {
	pdf_managed_fields.forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", read_only ? 1 : 0);
	});
}

async function apply_pdf_transaction(frm, transaction) {
	await frm.set_value({
		transaction_reference: transaction.transaction_reference,
		transaction_type: transaction.transaction_type,
		isin: transaction.isin,
		portfolio_name: transaction.portfolio_name,
		trade_date: transaction.trade_date,
		settlement_date: transaction.settlement_date,
		quantity_face_value: transaction.quantity_face_value,
		price: transaction.price,
		accrued_interest_paid: transaction.accrued_interest_paid,
		commission: transaction.commission,
	});
	set_pdf_fields_read_only(frm, true);
	frappe.show_alert({
		message: __("Bond transaction values read from PDF"),
		indicator: "green",
	});
}

function show_transaction_selection(frm, transactions) {
	const dialog = new frappe.ui.Dialog({
		title: __("Select Bond Transactions"),
		fields: [
			{
				fieldname: "transactions",
				fieldtype: "Table",
				label: __("Transactions to post"),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: true,
				data: transactions.map((transaction) => ({
					post: 1,
					...transaction,
				})),
				fields: [
					{
						fieldname: "post",
						fieldtype: "Check",
						label: __("Post"),
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldname: "transaction_reference",
						fieldtype: "Data",
						label: __("Reference"),
						read_only: 1,
						in_list_view: 1,
						columns: 2,
					},
					{
						fieldname: "transaction_type",
						fieldtype: "Data",
						label: __("Type"),
						read_only: 1,
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldname: "isin",
						fieldtype: "Data",
						label: __("ISIN"),
						read_only: 1,
						in_list_view: 1,
						columns: 2,
					},
					{
						fieldname: "quantity_face_value",
						fieldtype: "Float",
						label: __("Quantity"),
						read_only: 1,
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldname: "price",
						fieldtype: "Float",
						label: __("Price"),
						read_only: 1,
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldname: "portfolio_name",
						fieldtype: "Link",
						options: "Bond Portfolio",
						label: __("Post to Portfolio"),
						reqd: 1,
						in_list_view: 1,
						columns: 2,
					},
				],
			},
		],
		primary_action_label: __("Post Selected Transactions"),
		primary_action: async (values) => {
			const selections = (values.transactions || [])
				.filter((row) => row.post)
				.map((row) => ({
					transaction_reference: row.transaction_reference,
					portfolio_name: row.portfolio_name,
				}));
			if (!selections.length) {
				frappe.msgprint(__("Select at least one transaction."));
				return;
			}

			const selected_transaction = transactions.find(
				(row) => row.transaction_reference === selections[0].transaction_reference
			);
			if (
				selections.length === 1 &&
				selections[0].portfolio_name === selected_transaction.portfolio_name
			) {
				await apply_pdf_transaction(frm, {
					...selected_transaction,
					portfolio_name: selections[0].portfolio_name,
				});
				dialog.hide();
				return;
			}

			dialog.disable_primary_action();
			try {
				const { message: created } = await frm.call("create_selected_pdf_transactions", {
					transaction_selections: selections,
				});
				dialog.hide();
				frm.doc.__unsaved = 0;
				frappe.show_alert({
					message: __("Created {0} Bond Transactions", [created.length]),
					indicator: "green",
				});
				frappe.set_route("List", "Bond Transaction", {
					name: ["in", created],
				});
			} finally {
				dialog.enable_primary_action();
			}
		},
	});
	dialog.show();
	return Promise.resolve();
}

function get_calculation_state(frm) {
	if (!transaction_calculation_state.has(frm)) {
		transaction_calculation_state.set(frm, {
			request_id: 0,
			setting_default_accrued_interest: false,
			accrued_interest_was_defaulted: false,
		});
	}

	return transaction_calculation_state.get(frm);
}

function calculate_all(frm) {
	const state = get_calculation_state(frm);
	return request_calculation(frm, state, true);
}

function calculate_after_accrued_interest_change(frm) {
	const state = get_calculation_state(frm);
	if (state.setting_default_accrued_interest) {
		return Promise.resolve();
	}

	// From this point the value is a deliberate user override, including zero.
	state.accrued_interest_was_defaulted = false;
	return request_calculation(frm, state, true);
}

async function request_calculation(frm, state, allow_accrued_interest_default) {
	const request_id = ++state.request_id;
	const inputs = {
		isin: frm.doc.isin,
		settlement_date: frm.doc.settlement_date,
		quantity_face_value: frm.doc.quantity_face_value,
		price: frm.doc.price,
		accrued_interest_paid: frm.doc.accrued_interest_paid,
		commission: frm.doc.commission,
		transaction_name: frm.doc.name,
	};
	const response = await frappe.call({
		method: transaction_calculation_method,
		type: "POST",
		args: inputs,
	});

	// This value-only endpoint cannot sync an older Document into the form. A
	// slower response for an older edit is discarded before any values are set.
	if (request_id !== state.request_id) {
		return response.message;
	}

	const amounts = response.message;
	if (!amounts) {
		return amounts;
	}

	await frm.set_value({
		principal: amounts.principal,
		commission_amount: amounts.commission_amount,
		settlement_amount: amounts.settlement_amount,
		accrued_interest_calculated: amounts.accrued_interest_calculated,
	});

	if (request_id !== state.request_id) {
		return amounts;
	}

	const accrued_interest_is_unset =
		frm.doc.accrued_interest_paid === null ||
		frm.doc.accrued_interest_paid === undefined ||
		frm.doc.accrued_interest_paid === "";
	const has_calculated_accrued_interest =
		amounts.accrued_interest_calculated !== null &&
		amounts.accrued_interest_calculated !== undefined;
	const accrued_interest_inputs_are_ready =
		inputs.isin && inputs.settlement_date && Number(inputs.quantity_face_value) > 0;

	if (
		allow_accrued_interest_default &&
		accrued_interest_inputs_are_ready &&
		(accrued_interest_is_unset || state.accrued_interest_was_defaulted) &&
		has_calculated_accrued_interest
	) {
		state.setting_default_accrued_interest = true;
		try {
			await frm.set_value("accrued_interest_paid", amounts.accrued_interest_calculated);
			state.accrued_interest_was_defaulted = true;
		} finally {
			state.setting_default_accrued_interest = false;
		}

		if (request_id === state.request_id) {
			// The bank price includes commission, while accrued interest remains a
			// separate settlement component. Recalculate after applying its default.
			return request_calculation(frm, state, false);
		}
	}

	return amounts;
}
