context("Portfolio Performance", () => {
	before(() => {
		cy.login();
	});

	it("copies XIRR cash flows from the report", () => {
		cy.visit("/desk/query-report/Portfolio%20Performance");
		cy.window().should("have.property", "copy_xirr_cashflows").then((window) => {
			const call = cy.stub(window.frappe, "call").resolves({
				message: [
					{
						isin: "TEST-BOND",
						transaction_type: "purchase",
						date: "2025-12-31",
						amount: -1000,
					},
				],
			});
			const copy = cy.stub(window.frappe.utils, "copy_to_clipboard");
			const report = {
				get_values: () => ({
					portfolio: "TEST-PORTFOLIO",
					valuation_date: "2025-12-31",
				}),
			};

			return cy.wrap(window.copy_xirr_cashflows(report, "TEST-BOND", "past")).then(() => {
				expect(call).to.have.been.calledWithMatch({
					type: "POST",
					args: { isin: "TEST-BOND", xirr_type: "past" },
				});
				expect(copy).to.have.been.calledWithMatch(
					"isin\ttransaction_type\tdate\tamount\nTEST-BOND\tpurchase\t2025-12-31\t-1000"
				);
			});
		});
	});
});
