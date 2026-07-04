// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt


frappe.ui.form.on('Bond Master', {
    refresh: function(frm) {
        update_maturity_date(frm);
        hide_grid_buttons(frm);
    }
});

frappe.ui.form.on('Bond Principal Schedule', {
    principal_units: function(frm, cdt, cdn) {
        update_percentages(frm);
    }
});

function update_percentages(frm) {
    let total = 0;

    frm.doc.principal_schedule.forEach(row => {
        total += row.principal_units || 0;
    });

    if (!total) return;

    frm.doc.principal_schedule.forEach(row => {
        row.repayment_percent = (row.principal_units / total) * 100;
    });

    frm.refresh_field('principal_schedule');
}

frappe.ui.form.on('Bond Principal Schedule', {
    repayment_date: function(frm, cdt, cdn) {
        update_maturity_date(frm);
        update_percentages(frm)
    },
    principal_schedule_add: function(frm, cdt, cdn) {
        update_maturity_date(frm);
        update_percentages(frm)
    },
    principal_schedule_remove: function(frm) {
        update_maturity_date(frm);
        update_percentages(frm)
    }
});

function update_maturity_date(frm) {
    let max_date = null;

    (frm.doc.principal_schedule || []).forEach(row => {
        if (row.repayment_date) {
            if (!max_date || row.repayment_date > max_date) {
                max_date = row.repayment_date;
            }
        }
    });

    frm.set_value('maturity_date', max_date || null);
}
function hide_grid_buttons(frm) {
    let grid = frm.get_field("coupon_schedule").grid;

        // hide Buttons
        grid.wrapper.find('.grid-add-row').hide();
        grid.wrapper.find('.grid-remove-rows').hide();
        grid.wrapper.find('.grid-edit-rows').hide();
        grid.wrapper.find('.grid-duplicate-rows').hide();

        // also prevent row insert/delete programmatically via UI
        grid.cannot_add_rows = true;
        grid.cannot_delete_rows = true;
        grid.cannot_edit_rows = true;
        grid.cannot_duplicate_rows = true;
}