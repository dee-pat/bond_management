context("Investor navigation", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/desk/bond-investor");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.get(".page-head").should("be.visible");
	});

	it("links from Desk to the Vue investor app", () => {
		cy.get(".page-head .bond-investor-app-link")
			.should("be.visible")
			.and("have.attr", "href", "/bond-investor")
			.and("contain", "Open Investor App");
	});
});
