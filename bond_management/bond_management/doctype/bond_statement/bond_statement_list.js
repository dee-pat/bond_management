frappe.listview_settings["Bond Statement"] = {
	formatters: {
		reconciliation_status(value) {
			if (!value) {
				return "";
			}

			const color = {
				Matched: "green",
				Mismatched: "red",
			}[value];
			const label = frappe.utils.escape_html(__(value));
			const filter = frappe.utils.escape_html(`reconciliation_status,=,${value}`);

			return `<span class="filterable indicator-pill ${color || "gray"} ellipsis"
				data-filter="${filter}">
				<span class="ellipsis"> ${label} </span>
			</span>`;
		},
	},
};
