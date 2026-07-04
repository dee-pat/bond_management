// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Bond Statement", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("Bond Statement", {
    refresh(frm) {
        let grid = frm.get_field("bond_statement_details").grid;

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
});