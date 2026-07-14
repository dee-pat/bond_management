const redirect_investor_from_generic_desk = () => {
	const is_investor = frappe.user_roles?.includes("Bond Investor Read Only");
	const is_generic_desk = window.location.pathname.replace(/\/$/, "") === "/desk";

	if (is_investor && is_generic_desk) {
		window.location.replace("/desk/bond-investor");
	}
};

// Cypress loads app scripts with a minimal Frappe object that does not expose
// ``frappe.ready``. The redirect is only needed in a fully booted Desk session.
if (typeof frappe.ready === "function") {
	frappe.ready(redirect_investor_from_generic_desk);
}
