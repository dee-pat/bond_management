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

	it("exposes withholding tax as a zero-default percentage", () => {
		cy.window().should((window) => {
			const field = window.cur_frm.get_field("withholding_tax");
			expect(field).to.exist;
			expect(field.df.fieldtype).to.equal("Percent");
			expect(String(field.df.default)).to.equal("0");
		});
	});

	it("applies a server-normalized first coupon date through the form setter", () => {
		cy.intercept(
			"POST",
			"**/api/method/bond_management.bond_management.doctype.bond_master.bond_master.get_recalculated_schedules",
			{
				statusCode: 200,
				body: {
					message: {
						quantity_change: 0,
						maturity_date: "2027-01-01",
						first_coupon_date: "2025-01-03",
						principal_schedule: [],
						coupon_schedule: [],
					},
				},
			}
		).as("recalculateSchedules");

		cy.window().then((window) => {
			const frm = window.cur_frm;
			frm.doc.issue_date = "2025-01-01";
			frm.doc.face_value_per_unit = 100;
			frm.doc.coupon_frequency = "2";
			frm.doc.day_count_convention = "30E/360";
			frm.add_child("principal_schedule", {
				repayment_date: "2027-01-01",
				principal_units: 100,
			});
			cy.spy(frm, "set_value").as("setValue");

			return frm.script_manager.trigger("first_coupon_date");
		});

		cy.wait("@recalculateSchedules");
		cy.get("@setValue").should("have.been.calledWith", "first_coupon_date", "2025-01-03");
		cy.window().should((window) => expect(window.cur_frm.is_dirty()).to.equal(true));
	});
});
