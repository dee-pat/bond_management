frappe.ready(() => {
	const is_investor = frappe.user_roles?.includes("Bond Investor Read Only");
	const is_generic_desk = window.location.pathname.replace(/\/$/, "") === "/desk";

	if (is_investor && is_generic_desk) {
		window.location.replace("/desk/bond-investor");
	}
});
