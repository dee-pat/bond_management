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
    },
    copy_cashflows(frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        frm.call({
            method: "get_cashflows",
            doc: frm.doc,
            args: {
                isin: row.isin,
                market_price: row.market_price
            }
        }).then(r => {
            const data = r.message || [];

            if (!data.length) {
                frappe.msgprint("No cashflows found.");
                return;
            }

            // sort by date
            data.sort((a, b) => new Date(a.date) - new Date(b.date));

            let tsv = "isin\ttransaction_type\tdate\tamount\n";

            data.forEach(d => {
                tsv += `${d.isin}\t${d.type}\t${d.date}\t${d.amount}\n`;
            });

            fallbackCopy(tsv);

            frappe.show_alert({
                message: `Copied for ${row.isin}`,
                indicator: "green"
            });
        });
    }
});


function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = 0;

    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
}