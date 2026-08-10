context("Portfolio Performance", () => {
	beforeEach(() => {
		cy.login();
	});

	it("copies cash flows by clicking the rendered XIRR button", () => {
		cy.intercept("GET", "**/api/method/frappe.client.validate_link_and_fetch*", {
			statusCode: 200,
			body: { message: { name: "TEST-PORTFOLIO" } },
		});
		cy.intercept("GET", "**/api/method/frappe.desk.query_report.run*", {
			statusCode: 200,
			body: {
				message: {
					columns: [
						{
							label: "ISIN",
							fieldname: "isin",
							fieldtype: "Data",
							width: 160,
						},
						{
							label: "XIRR",
							fieldname: "xirr",
							fieldtype: "Percent",
							width: 100,
						},
						{
							label: "XIRR (USD)",
							fieldname: "xirr_usd",
							fieldtype: "Percent",
							width: 120,
						},
					],
					result: [
						{
							isin: "TEST-BOND",
							xirr: 12.5,
							xirr_usd: 8.75,
						},
					],
					execution_time: 0.01,
				},
			},
		}).as("report");
		cy.intercept(
			"POST",
			"**/api/method/bond_management.bond_management.report.portfolio_performance.portfolio_performance.get_xirr_cashflows",
			{
				statusCode: 200,
				body: {
					message: [
						{
							isin: "=TEST\tBOND\nALERT",
							transaction_type: "+purchase",
							date: "2025-12-31",
							currency: "@USD",
							amount: -1000,
							quantity: 10,
							rate: -100,
						},
					],
				},
			}
		).as("cashflows");

		cy.visit(
			"/desk/query-report/Portfolio%20Performance?portfolio=TEST-PORTFOLIO&valuation_date=2025-12-31"
		);
		cy.wait("@report");
		cy.window().then((window) => {
			cy.stub(window.frappe.utils, "copy_to_clipboard").as("copyToClipboard");
		});

		cy.get(
			'.portfolio-cashflow-copy[data-xirr-type="past"][data-cashflow-currency="reporting"]'
		)
			.should("be.visible")
			.click();

		cy.wait("@cashflows").then(({ request }) => {
			const body = parse_request_body(request.body);
			expect(body).to.include({
				portfolio: "TEST-PORTFOLIO",
				valuation_date: "2025-12-31",
				isin: "TEST-BOND",
				xirr_type: "past",
				cashflow_currency: "reporting",
			});
		});
		cy.get("@copyToClipboard").should(
			"have.been.calledWith",
			"isin\ttransaction_type\tdate\tcurrency\tamount\tquantity\trate\n'=TEST BOND ALERT\t'+purchase\t2025-12-31\t'@USD\t-1000\t10\t-100",
			"Copied 1 cash flows"
		);
	});

	it("hides duplicate USD columns for a USD-only portfolio", () => {
		cy.intercept("GET", "**/api/method/frappe.client.validate_link_and_fetch*", {
			statusCode: 200,
			body: { message: { name: "TEST-PORTFOLIO" } },
		});
		cy.intercept("GET", "**/api/method/frappe.desk.query_report.run*", {
			statusCode: 200,
			body: {
				message: {
					columns: [
						{
							label: "ISIN",
							fieldname: "isin",
							fieldtype: "Data",
							width: 160,
						},
						{
							label: "Market Value",
							fieldname: "market_value",
							fieldtype: "Currency",
							width: 135,
						},
						{
							label: "XIRR",
							fieldname: "xirr",
							fieldtype: "Percent",
							width: 80,
						},
					],
					result: [{ isin: "TEST-BOND", market_value: 100, xirr: 12.5 }],
					execution_time: 0.01,
				},
			},
		}).as("usdOnlyReport");

		cy.visit(
			"/desk/query-report/Portfolio%20Performance?portfolio=TEST-PORTFOLIO&valuation_date=2025-12-31"
		);
		cy.wait("@usdOnlyReport");
		cy.get(".dt-cell--header .dt-cell__content").should("not.contain", "Market Value (USD)");
		cy.get(".dt-cell--header .dt-cell__content").should("not.contain", "XIRR (USD)");
	});
});

function parse_request_body(body) {
	if (typeof body !== "string") {
		return body;
	}

	return Object.fromEntries(new URLSearchParams(body));
}
