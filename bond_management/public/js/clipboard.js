// Copyright (c) 2026, Deepak Patel and contributors
// For license information, please see license.txt

(function () {
	const app = (globalThis.bond_management ??= {});
	const utils = (app.utils ??= {});
	const clipboard = (utils.clipboard ??= {});
	if (clipboard.sanitize) {
		return;
	}

	clipboard.sanitize = function (value, options = {}) {
		const controls = options.unicodeControls ? /\p{Cc}/gu : /[\u0000-\u001f\u007f]/g;
		const text = String(value ?? "").replace(controls, " ");
		if (options.numeric && /^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(text)) {
			return text;
		}
		return /^[=+\-@]/.test(text) ? `'${text}` : text;
	};
})();
