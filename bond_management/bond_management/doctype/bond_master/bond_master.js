// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

const schedule_recalculation_state = new WeakMap();
const schedule_recalculation_method =
	"bond_management.bond_management.doctype.bond_master.bond_master.get_recalculated_schedules";

frappe.ui.form.on("Bond Master", {
	issue_date: recalculate_schedules,
	first_coupon_date: recalculate_schedules,
	coupon_frequency: recalculate_schedules,
	coupon_rate: recalculate_schedules,
	currency: update_quantity_change,
	day_count_convention: (frm) =>
		update_quantity_change(frm).then(() => recalculate_schedules(frm)),
});

frappe.ui.form.on("Bond Principal Schedule", {
	principal_units: recalculate_schedules,
	repayment_date: recalculate_schedules,
	principal_schedule_add: recalculate_schedules,
	principal_schedule_remove: recalculate_schedules,
});

function get_schedule_state(frm) {
	if (!schedule_recalculation_state.has(frm)) {
		schedule_recalculation_state.set(frm, {
			request_id: 0,
		});
	}

	return schedule_recalculation_state.get(frm);
}

function schedules_are_ready(frm) {
	const rows = frm.doc.principal_schedule || [];
	return (
		frm.doc.issue_date &&
		frm.doc.face_value_per_unit &&
		frm.doc.coupon_frequency &&
		frm.doc.day_count_convention &&
		rows.length > 0 &&
		rows.every(
			(row) =>
				row.repayment_date &&
				row.principal_units !== null &&
				row.principal_units !== undefined &&
				row.principal_units !== ""
		)
	);
}

function recalculate_schedules(frm) {
	const state = get_schedule_state(frm);
	const request_id = ++state.request_id;
	if (!schedules_are_ready(frm)) {
		return Promise.resolve();
	}

	const document_snapshot = JSON.stringify(frm.doc);

	return frappe
		.call({
			method: schedule_recalculation_method,
			type: "POST",
			args: { doc: document_snapshot },
		})
		.then((response) => {
			if (request_id !== state.request_id) {
				return response.message;
			}

			return apply_recalculated_schedules(frm, state, request_id, response.message);
		});
}

function update_quantity_change(frm) {
	const kenyaConvention = ["act/364(kenya)", "actual/364(kenya)"].includes(
		String(frm.doc.day_count_convention || "").toLowerCase()
	);
	return frm.set_value(
		"quantity_change",
		String(frm.doc.currency || "").toUpperCase() === "KES" && kenyaConvention ? 1 : 0
	);
}

async function apply_recalculated_schedules(frm, state, request_id, schedules) {
	if (!schedules) {
		return schedules;
	}
	if (request_id !== state.request_id) {
		return schedules;
	}

	await frm.set_value("quantity_change", schedules.quantity_change ? 1 : 0);
	if (request_id !== state.request_id) {
		return schedules;
	}

	await frm.set_value("maturity_date", schedules.maturity_date);
	if (request_id !== state.request_id) {
		return schedules;
	}

	if (schedules.first_coupon_date && frm.doc.first_coupon_date !== schedules.first_coupon_date) {
		frm.doc.first_coupon_date = schedules.first_coupon_date;
		frm.refresh_field("first_coupon_date");
	}

	await apply_principal_percentages(frm, state, request_id, schedules.principal_schedule || []);
	if (request_id !== state.request_id) {
		return schedules;
	}

	await frm.set_value("coupon_schedule", schedules.coupon_schedule || []);
	frm.refresh_field("maturity_date");
	frm.refresh_field("principal_schedule");
	frm.refresh_field("coupon_schedule");

	return schedules;
}

async function apply_principal_percentages(frm, state, request_id, calculated_rows) {
	const rows_by_name = new Map(
		calculated_rows.filter((row) => row.name).map((row) => [row.name, row])
	);
	const rows_by_index = new Map(calculated_rows.map((row) => [row.idx, row]));
	for (const row of frm.doc.principal_schedule || []) {
		if (request_id !== state.request_id) {
			return;
		}
		const calculated = rows_by_name.get(row.name) || rows_by_index.get(row.idx);
		if (!calculated) {
			continue;
		}

		await frappe.model.set_value(
			row.doctype,
			row.name,
			"repayment_percent",
			calculated.repayment_percent
		);
	}
}
