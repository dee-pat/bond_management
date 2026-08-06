context("Bond Master", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/desk/bond-master/new");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.window().should((window) => {
			expect(window.cur_frm?.doctype).to.equal("Bond Master");
		});
	});

	it("derives quantity change from KES and the Kenya day-count convention", () => {
		cy.window().then(async (window) => {
			const frm = window.cur_frm;
			frm.doc.currency = "KES";
			frm.doc.day_count_convention = "Actual/364(Kenya)";
			await frm.script_manager.trigger("day_count_convention");
			expect(frm.doc.quantity_change).to.equal(1);

			frm.doc.currency = "USD";
			await frm.script_manager.trigger("currency");
			expect(frm.doc.quantity_change).to.equal(0);
		});
	});
});
