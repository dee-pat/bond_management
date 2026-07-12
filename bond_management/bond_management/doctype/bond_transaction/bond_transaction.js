// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bond Transaction", {
    face_value_per_unit: calculate_all,
 	quantity_face_value: calculate_all,
    price: calculate_all,
    accrued_interest_paid: calculate_all,
    commission: calculate_all,
    settlement_date: calculate_all,
    isin: calculate_all,
 });


function calculate_all(frm) {
    frm.call("calculate_amounts").then((r) => {
        const amounts = r.message;
        if (!amounts) return;

        frm.set_value("principal", amounts.principal);
        frm.set_value("commission_amount", amounts.commission_amount);
        frm.set_value("settlement_amount", amounts.settlement_amount);
        frm.set_value("accrued_interest_calculated", amounts.accrued_interest_calculated);
        if (!frm.doc.accrued_interest_paid && amounts.accrued_interest_calculated) {
            frm.set_value("accrued_interest_paid", amounts.accrued_interest_calculated);
        }
    });
}

