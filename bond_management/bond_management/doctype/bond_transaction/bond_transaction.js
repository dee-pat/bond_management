// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

const transaction_calculation_state = new WeakMap();
const transaction_calculation_method =
	"bond_management.bond_management.doctype.bond_transaction.bond_transaction.get_calculated_amounts";

frappe.ui.form.on("Bond Transaction", {
	face_value_per_unit: calculate_all,
	quantity_face_value: calculate_all,
	price: calculate_all,
	accrued_interest_paid: calculate_after_accrued_interest_change,
	commission: calculate_all,
	settlement_date: calculate_all,
	isin: calculate_all,
});

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
