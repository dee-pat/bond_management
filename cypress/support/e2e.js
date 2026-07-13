Cypress.Commands.add("login", (email, password) => {
	const resolved_email =
		email || Cypress.env("testUser") || Cypress.config("testUser") || "Administrator";
	const resolved_password =
		password || Cypress.env("adminPassword") || Cypress.config("adminPassword") || "admin";

	return cy.session(
		[resolved_email, resolved_password],
		() =>
			cy.request({
				method: "POST",
				url: "/api/method/login",
				body: {
					usr: resolved_email,
					pwd: resolved_password,
				},
			}),
		{
			validate: () =>
				cy
					.request("/api/method/frappe.auth.get_logged_user")
					.its("body.message")
					.should("eq", resolved_email),
		}
	);
});
