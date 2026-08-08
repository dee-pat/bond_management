context("Bond Exchange Rate", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/desk/bond-exchange-rate/new");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.window().should((window) => {
			expect(window.cur_frm?.doctype).to.equal("Bond Exchange Rate");
		});
	});

	it("syncs canonical rate from reverse rate input", () => {
		cy.window().then(async (window) => {
			const frm = window.cur_frm;
			frm.doc.reverse_rate = 129.45;
			await frm.script_manager.trigger("reverse_rate");

			expect(Number(frm.doc.rate)).to.be.closeTo(1 / 129.45, 1e-12);
			expect(Number(frm.doc.reverse_rate)).to.equal(129.45);
		});
	});
});
