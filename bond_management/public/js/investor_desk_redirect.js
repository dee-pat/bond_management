const INVESTOR_APP_PATH = "/bond-investor";
const INVESTOR_ROLE = "Bond Investor Read Only";
const INVESTOR_APP_ROLES = new Set([INVESTOR_ROLE, "Bond Management Manager"]);

const is_investor_app_user = () =>
	frappe.session?.user === "Administrator" ||
	frappe.user_roles?.some((role) => INVESTOR_APP_ROLES.has(role));

const redirect_investor_from_generic_desk = () => {
	const is_investor = frappe.user_roles?.includes(INVESTOR_ROLE);
	const is_generic_desk = window.location.pathname.replace(/\/$/, "") === "/desk";

	if (is_investor && is_generic_desk) {
		window.location.replace(INVESTOR_APP_PATH);
	}
};

const add_investor_app_link = () => {
	if (!is_investor_app_user()) return;

	const link = document.createElement("a");
	link.href = INVESTOR_APP_PATH;
	link.title = "Open Investor App";
	link.setAttribute("aria-label", "Open Investor App");
	link.textContent = "Open Investor App";

	const pageActions = [...document.querySelectorAll(".page-head .page-actions")].find(
		(element) => element.getClientRects().length > 0
	);
	if (pageActions && !pageActions.querySelector(".bond-investor-app-link")) {
		link.className = "btn btn-default btn-sm bond-investor-app-link";
		pageActions.insertBefore(link, pageActions.querySelector(".standard-actions"));
		return;
	}

	const desktopActions = document.querySelector(".desktop-navbar > .flex");
	if (!desktopActions || desktopActions.querySelector(".bond-investor-app-link")) return;

	link.className = "btn-reset nav-link text-muted bond-investor-app-link";
	desktopActions.insertBefore(link, desktopActions.querySelector(".desktop-notifications"));
};

if (typeof $ === "function") {
	$(document).on("app_ready.investorNavigation", redirect_investor_from_generic_desk);

	// Desk recreates this header when the desktop workspace is shown.
	$(document).on("desktop_screen.investorNavigation", add_investor_app_link);
	$(document).on("page-change.investorNavigation", add_investor_app_link);
}
