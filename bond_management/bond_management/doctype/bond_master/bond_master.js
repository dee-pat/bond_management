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
	day_count_convention: recalculate_schedules,
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

async function apply_recalculated_schedules(frm, state, request_id, schedules) {
	if (!schedules) {
		return schedules;
	}

	await frm.set_value("maturity_date", schedules.maturity_date);
	if (request_id !== state.request_id) {
		return schedules;
	}

	await apply_principal_percentages(frm, schedules.principal_schedule || []);
	if (request_id !== state.request_id) {
		return schedules;
	}

	await frm.set_value("coupon_schedule", schedules.coupon_schedule || []);
	frm.refresh_field("maturity_date");
	frm.refresh_field("principal_schedule");
	frm.refresh_field("coupon_schedule");

	return schedules;
}

function apply_principal_percentages(frm, calculated_rows) {
	const rows_by_name = new Map(
		calculated_rows.filter((row) => row.name).map((row) => [row.name, row])
	);
	const rows_by_index = new Map(calculated_rows.map((row) => [row.idx, row]));
	const updates = (frm.doc.principal_schedule || []).map((row) => {
		const calculated = rows_by_name.get(row.name) || rows_by_index.get(row.idx);
		if (!calculated) {
			return Promise.resolve();
		}

		return frappe.model.set_value(
			row.doctype,
			row.name,
			"repayment_percent",
			calculated.repayment_percent
		);
	});

	return Promise.all(updates);
}
