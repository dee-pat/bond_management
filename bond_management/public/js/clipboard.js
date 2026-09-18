// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

frappe.provide("bond_management.utils.clipboard").sanitize = function (value, options = {}) {
	const text = String(value ?? "").replace(/[\u0000-\u001f\u007f]/g, " ");
	if (options.numeric && /^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(text)) {
		return text;
	}
	return /^[=+\-@]/.test(text) ? `'${text}` : text;
};
