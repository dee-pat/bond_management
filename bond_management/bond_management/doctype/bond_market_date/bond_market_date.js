// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt



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




frappe.ui.form.on('Bond Market Date', {
    refresh: function(frm) {
        render_yield_curve(frm);
    }
});

function render_yield_curve(frm) {

    const field = frm.fields_dict.yield_curve_chart;
    if (!field) return;

    let wrapper = field.$wrapper;
    wrapper.empty();

    let rows = frm.doc.bond_market_prices || [];
    if (!rows.length) {
        wrapper.html("No data");
        return;
    }

    let valuation_date = frm.doc.date;

    // Build dataset
    let data = rows.map(row => {

        let date = row.weighted_avg_repayment_date || row.maturity_date;
        let years = frappe.datetime.get_day_diff(date, valuation_date) / 365;

        return {
            isin: row.isin,
            date: date,
            years: years,
            yield: parseFloat(row.future_xirr / 100)
        };

    }).filter(d => d.years > 0 && !isNaN(d.yield));

    if (!data.length) {
        wrapper.html("No valid data");
        return;
    }

    // Sort by maturity (IMPORTANT)
    data.sort((a, b) => a.years - b.years);

    // X axis = years (REAL spacing)
    const labels = data.map(d => {
        return `${d.date}\n${d.isin}`;
    });

    // Y axis = %
    const values = data.map(d => d.yield * 100);

    // Build tooltip labels (dates + isin)
    const tooltip_labels = data.map(d => {
        return `${d.date} | ${d.isin}`;
    });

    // Create container
    let container = $('<div>').css({ height: '340px' });
    wrapper.append(container);

    // Render chart
    let chart = new frappe.Chart(container[0], {
        title: "Yield Curve",
        data: {
            labels: labels,
            datasets: [
                {
                    name: "Yield (%)",
                    values: values
                }
            ]
        },
        type: 'line',
        height: 340,
        colors: ['#3366ff'],
        lineOptions: {
            spline: 1
        }
    });
 

    // Inject custom tooltip
    chart.parent.querySelectorAll('.chart-point').forEach((point, i) => {
        point.setAttribute('title', tooltip_labels[i]);
    });

}