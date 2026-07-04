// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Bond Market Date", {
// 	refresh(frm) {

// 	},
// });

let x_timeout;

frappe.ui.form.on("Bond Market Prices", {
    market_price(frm) {
        clearTimeout(x_timeout);

        x_timeout = setTimeout(() => {
            frm.call("update_future_xirr").then(() => {
                frm.refresh_field("bond_market_prices");
            });
        }, 500);  // wait 0.5s after typing
    },
    isin(frm) {
        clearTimeout(x_timeout);

        x_timeout = setTimeout(() => {
            frm.call("update_principal_factor").then(() => {
                frm.refresh_field("bond_market_prices");
            });
        }, 500);
    }
});
