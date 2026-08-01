context("Bond Statement", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/desk/bond-statement/new");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.window().should((window) => {
			expect(window.cur_frm?.doctype).to.equal("Bond Statement");
			expect(
				window.frappe.ui.form.handlers["Bond Statement"]?.attachment
			).to.have.length.greaterThan(0);
		});
	});

	it("reads the portfolio and date when a PDF is attached", () => {
		cy.get('.frappe-control[data-fieldname="attachment"] .attached-file')
			.should("have.css", "min-height", "56px")
			.find(".attached-file-link")
			.should("have.css", "white-space", "normal")
			.and("have.css", "overflow-wrap", "anywhere");

		cy.window().then((window) => {
			const frm = window.cur_frm;
			expect(frm.get_field("portfolio_name").df.read_only).to.equal(1);
			expect(frm.get_field("statement_date").df.read_only).to.equal(1);
			expect(frm.get_field("market_price_posting").df.read_only).to.equal(1);

			cy.stub(frm, "call")
				.withArgs("read_statement_pdf")
				.resolves({
					message: {
						portfolio_name: "Nanda",
						statement_date: "2026-06-30",
						account_no: "1110700431102",
					},
				})
				.as("readStatementPdf");

			frm.doc.attachment = "/private/files/statement.pdf";
			frm.refresh_field("attachment");
			return frm.script_manager.trigger("attachment");
		});

		cy.get("@readStatementPdf").should("have.been.calledOnce");
		cy.window().then((window) => {
			expect(window.cur_frm.doc.portfolio_name).to.equal("Nanda");
			expect(window.cur_frm.doc.statement_date).to.equal("2026-06-30");
		});
	});

	it("clears derived fields when the attachment is removed", () => {
		cy.window().then((window) => {
			const frm = window.cur_frm;
			frm.doc.portfolio_name = "Nanda";
			frm.doc.statement_date = "2026-06-30";
			frm.doc.attachment = null;

			return frm.script_manager.trigger("attachment");
		});

		cy.window().then((window) => {
			expect(window.cur_frm.doc.portfolio_name ?? null).to.be.null;
			expect(window.cur_frm.doc.statement_date ?? null).to.be.null;
		});
	});

	it("ignores a stale PDF response after a newer attachment is selected", () => {
		cy.window().then((window) => {
			const frm = window.cur_frm;
			let resolve_first;
			const first_response = new Promise((resolve) => {
				resolve_first = resolve;
			});
			let call_count = 0;
			cy.stub(frm, "call")
				.withArgs("read_statement_pdf")
				.callsFake(() => {
					call_count += 1;
					return call_count === 1
						? first_response
						: Promise.resolve({
								message: {
									portfolio_name: "Newest Portfolio",
									statement_date: "2026-07-31",
								},
						  });
				})
				.as("readStatementPdfWithDelay");

			frm.doc.attachment = "/private/files/first.pdf";
			const first_trigger = frm.script_manager.trigger("attachment");
			frm.doc.attachment = "/private/files/second.pdf";
			const second_trigger = frm.script_manager.trigger("attachment");

			return second_trigger.then(() => {
				resolve_first({
					message: {
						portfolio_name: "Stale Portfolio",
						statement_date: "2026-01-01",
					},
				});
				return first_trigger;
			});
		});

		cy.window().then((window) => {
			expect(window.cur_frm.doc.portfolio_name).to.equal("Newest Portfolio");
			expect(window.cur_frm.doc.statement_date).to.equal("2026-07-31");
		});
	});

	it("colors reconciliation status in the list view", () => {
		cy.visit("/desk/bond-statement/view/list");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.window().should((window) => {
			expect(
				window.frappe.listview_settings["Bond Statement"]?.formatters
					?.reconciliation_status
			).to.be.a("function");
		});

		cy.window().then((window) => {
			const formatter =
				window.frappe.listview_settings["Bond Statement"]?.formatters
					?.reconciliation_status;

			const matched = window.$(formatter("Matched"));
			const mismatched = window.$(formatter("Mismatched"));

			expect(matched).to.have.class("green");
			expect(matched.attr("data-filter")).to.equal("reconciliation_status,=,Matched");
			expect(mismatched).to.have.class("red");
			expect(mismatched.attr("data-filter")).to.equal("reconciliation_status,=,Mismatched");
		});
	});
});
