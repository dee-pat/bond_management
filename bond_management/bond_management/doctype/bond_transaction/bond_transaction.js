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
    let principal = (frm.doc.face_value_per_unit || 0) * (frm.doc.quantity_face_value || 0);
    let commission_amount = principal * (frm.doc.commission || 0) / 100;
    let settlement = principal * (frm.doc.price || 0) / 100 + (frm.doc.accrued_interest_paid || 0);

    frm.set_value('principal', principal);
    frm.set_value('commission_amount', commission_amount);
    frm.set_value('settlement_amount', settlement);
    if (!frm.doc.isin || !frm.doc.settlement_date|| !frm.doc.quantity_face_value) return;

    frappe.call({
        method: "bond_management.bond_management.utils.accrual.get_accrued_interest",
        args: {
            isin: frm.doc.isin,
            settlement_date: frm.doc.settlement_date,
            quantity_face_value: frm.doc.quantity_face_value
        },
        callback: function(r) {
            if (r.message !== undefined) {
                frm.set_value("accrued_interest_calculated", r.message);
                if (frm.doc.accrued_interest_paid === undefined || frm.doc.accrued_interest_paid === "") {
                    frm.set_value("accrued_interest_paid", r.message);
                }
            }
        }
    });
}


