const exchange_rate_syncing = new WeakSet();

frappe.ui.form.on("Bond Exchange Rate", {
	rate: (frm) => sync_exchange_rate(frm, "rate", "reverse_rate"),
	reverse_rate: (frm) => sync_exchange_rate(frm, "reverse_rate", "rate"),
});

function sync_exchange_rate(frm, source_field, target_field) {
	if (exchange_rate_syncing.has(frm)) {
		return Promise.resolve();
	}

	exchange_rate_syncing.add(frm);
	const value = Number(frm.doc[source_field]);
	const reciprocal = Number.isFinite(value) && value !== 0 ? 1 / value : null;
	return frm
		.set_value(target_field, reciprocal)
		.finally(() => exchange_rate_syncing.delete(frm));
}
