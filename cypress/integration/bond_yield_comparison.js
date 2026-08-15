const USD_BOND = "TEST-BOND-USD";
const USD_BOND_TWO = "TEST-BOND-USD-TWO";
const KES_BOND = "TEST-BOND-KES";
const NO_OVERLAP_BOND = "TEST-BOND-NO-OVERLAP";
const NO_OVERLAP_BOND_TWO = "TEST-BOND-NO-OVERLAP-TWO";
const NO_OVERLAP_BOND_THREE = "TEST-BOND-NO-OVERLAP-THREE";
const NO_OVERLAP_BOND_FOUR = "TEST-BOND-NO-OVERLAP-FOUR";
const NO_OVERLAP_BOND_FIVE = "TEST-BOND-NO-OVERLAP-FIVE";
const NO_OVERLAP_BOND_SIX = "TEST-BOND-NO-OVERLAP-SIX";

const REPORT_ROWS = [
	{
		date: "2025-01-01",
		isin: USD_BOND,
		currency: "USD",
		market_price: 99,
		future_xirr: 8.25,
	},
	{
		date: "2025-01-01",
		isin: USD_BOND_TWO,
		currency: "USD",
		market_price: 100,
		future_xirr: 8.75,
	},
	{
		date: "2025-01-01",
		isin: KES_BOND,
		currency: "KES",
		market_price: 101,
		future_xirr: 11.5,
	},
	{
		date: "2025-02-01",
		isin: USD_BOND,
		currency: "USD",
		market_price: 98,
		future_xirr: 8.5,
	},
	{
		date: "2025-02-01",
		isin: USD_BOND_TWO,
		currency: "USD",
		market_price: 99,
		future_xirr: 9,
	},
	{
		date: "2025-02-01",
		isin: KES_BOND,
		currency: "KES",
		market_price: 100,
		future_xirr: 11.75,
	},
	{
		date: "2025-03-01",
		isin: USD_BOND,
		currency: "USD",
		market_price: 97,
		future_xirr: 8.75,
	},
	{
		date: "2025-04-01",
		isin: NO_OVERLAP_BOND,
		currency: "USD",
		market_price: 97,
		future_xirr: 8.75,
	},
	{
		date: "2025-05-01",
		isin: NO_OVERLAP_BOND_TWO,
		currency: "KES",
		market_price: 101,
		future_xirr: 11.5,
	},
	{
		date: "2025-06-01",
		isin: NO_OVERLAP_BOND,
		currency: "USD",
		market_price: 96,
		future_xirr: 9.25,
	},
	{
		date: "2025-06-01",
		isin: NO_OVERLAP_BOND_THREE,
		currency: "EUR",
		market_price: 101,
		future_xirr: 9.5,
	},
	{
		date: "2025-07-01",
		isin: NO_OVERLAP_BOND_TWO,
		currency: "KES",
		market_price: 100,
		future_xirr: 11.75,
	},
	{
		date: "2025-07-01",
		isin: NO_OVERLAP_BOND_FOUR,
		currency: "GBP",
		market_price: 101,
		future_xirr: 10.5,
	},
	{
		date: "2025-08-01",
		isin: NO_OVERLAP_BOND_THREE,
		currency: "EUR",
		market_price: 100,
		future_xirr: 9.75,
	},
	{
		date: "2025-08-01",
		isin: NO_OVERLAP_BOND_FIVE,
		currency: "JPY",
		market_price: 101,
		future_xirr: 12.5,
	},
	{
		date: "2025-09-01",
		isin: NO_OVERLAP_BOND_FOUR,
		currency: "GBP",
		market_price: 100,
		future_xirr: 10.75,
	},
	{
		date: "2025-09-01",
		isin: NO_OVERLAP_BOND_SIX,
		currency: "ZAR",
		market_price: 101,
		future_xirr: 13.5,
	},
	{
		date: "2025-10-01",
		isin: NO_OVERLAP_BOND_FIVE,
		currency: "JPY",
		market_price: 100,
		future_xirr: 12.75,
	},
	{
		date: "2025-11-01",
		isin: NO_OVERLAP_BOND_SIX,
		currency: "ZAR",
		market_price: 100,
		future_xirr: 13.75,
	},
];

context("Bond Yield Comparison", () => {
	beforeEach(() => {
		cy.login();
		cy.intercept("GET", "**/api/method/frappe.desk.search.search_link*", (request) => {
			const text = String(request.query.txt || "").toLowerCase();
			const options = [
				USD_BOND,
				USD_BOND_TWO,
				KES_BOND,
				NO_OVERLAP_BOND,
				NO_OVERLAP_BOND_TWO,
				NO_OVERLAP_BOND_THREE,
				NO_OVERLAP_BOND_FOUR,
				NO_OVERLAP_BOND_FIVE,
				NO_OVERLAP_BOND_SIX,
			]
				.filter((value) => value.toLowerCase().includes(text))
				.map((value) => ({ value, description: "Test bond" }));
			request.reply({ statusCode: 200, body: { message: options } });
		});
		cy.intercept("GET", "**/api/method/frappe.desk.query_report.run*", (request) => {
			const filters = parse_filters(request.query.filters);
			const selected_bonds = filters?.bonds || [];
			const rows = REPORT_ROWS.filter((row) => {
				if (selected_bonds.length && !selected_bonds.includes(row.isin)) {
					return false;
				}
				if (filters?.from_date && row.date < filters.from_date) {
					return false;
				}
				if (filters?.to_date && row.date > filters.to_date) {
					return false;
				}
				return true;
			});
			request.reply({
				statusCode: 200,
				body: {
					message: {
						columns: [
							{ label: "Date", fieldname: "date", fieldtype: "Date" },
							{ label: "ISIN", fieldname: "isin", fieldtype: "Link" },
							{ label: "CCY", fieldname: "currency", fieldtype: "Data" },
							{
								label: "Market Price",
								fieldname: "market_price",
								fieldtype: "Float",
							},
							{
								label: "Future XIRR",
								fieldname: "future_xirr",
								fieldtype: "Percent",
							},
						],
						result: rows,
						execution_time: 0.01,
					},
				},
			});
		}).as("yieldReport");
	});

	it("compares selected bonds and assigns one colour per currency", () => {
		let usd_color;
		cy.visit(
			"/desk/query-report/Bond%20Yield%20Comparison?from_date=2025-01-01&to_date=2025-03-01"
		);
		cy.wait("@yieldReport");

		cy.get('.page-form .multiselect-list[data-fieldname="bonds"]').should("not.exist");
		cy.get('[data-bond-yield-selection] .bond-yield-checkbox')
			.should("have.length", 3)
			.each(($checkbox) => cy.wrap($checkbox).should("be.checked"));
		cy.get("[data-bond-yield-select-all]").should("be.checked");
		cy.get("[data-bond-yield-selection] tbody").should("contain", "USD").and("contain", "KES");
		cy.window().then((window) => {
			const chart = window.frappe.query_report.chart;
			expect(chart.title).to.equal("Future XIRR (%) by Year");
			expect(chart.data.labels).to.deep.equal(["2025", "2025", "2025"]);
			chart.data.datasets.forEach((dataset) => {
				expect(dataset.values).to.not.include(0);
			});
			expect(chart.data.datasets.map((dataset) => dataset.name)).to.deep.equal([
				KES_BOND,
				USD_BOND,
				USD_BOND_TWO,
			]);
			expect(chart.colors[0]).to.not.equal(chart.colors[1]);
			expect(chart.colors[1]).to.equal(chart.colors[2]);
			usd_color = chart.colors[1];
		});
		cy.get(".chart-wrapper .chart-legend").should("not.exist");
		cy.get(`[data-bond-yield-selection] input[data-bond-yield-isin="${KES_BOND}"]`)
			.uncheck()
			.should("not.be.checked");
		cy.get("[data-bond-yield-select-all]").should("not.be.checked").and("have.prop", "indeterminate", true);
		cy.window().then((window) => {
			const chart = window.frappe.query_report.chart;
			expect(chart.data.datasets).to.have.length(2);
			expect(chart.data.datasets.map((dataset) => dataset.name)).to.deep.equal([
				USD_BOND,
				USD_BOND_TWO,
			]);
		});
		cy.get(`[data-bond-yield-selection] input[data-bond-yield-isin="${KES_BOND}"]`)
			.check()
			.should("be.checked");
		cy.get("[data-bond-yield-select-all]").should("be.checked");

		cy.window().then((window) => {
			const chart = window.frappe.query_report.chart;
			expect(chart).to.exist;
			expect(chart.data.labels).to.deep.equal(["2025", "2025", "2025"]);
			expect(chart.data.datasets).to.have.length(3);
			expect(chart.data.datasets.map((dataset) => dataset.name)).to.deep.equal([
				KES_BOND,
				USD_BOND,
				USD_BOND_TWO,
			]);
			expect(chart.colors[0]).to.not.equal(chart.colors[1]);
			expect(chart.colors[1]).to.equal(chart.colors[2]);
			expect(chart.colors[1]).to.equal(usd_color);
		});
		cy.get('[data-bond-yield-selection] .bond-yield-selection-summary').should(
			"contain",
			"3 of 3 bonds selected"
		);
		cy.window().then((window) => {
			cy.stub(window.frappe.utils, "copy_to_clipboard").as("copyAuditData");
		});
		cy.get("[data-copy-audit-data]").click();
		cy.get("@copyAuditData").should("have.been.calledOnce");
		cy.get("@copyAuditData").its("firstCall.args.0").should("contain", "Future XIRR");
		cy.get(".report-wrapper").should("not.be.visible");

		cy.get("[data-bond-yield-select-all]").uncheck();
		cy.get('[data-bond-yield-selection] .bond-yield-checkbox:checked').should("not.exist");
		cy.get("[data-bond-yield-select-all]").should("not.be.checked").and("have.prop", "indeterminate", false);
		cy.get(".chart-wrapper").should(
			"contain",
			"Select one or more bonds to display their stored Future XIRR."
		);
		cy.get("[data-bond-yield-select-all]").check().should("be.checked");
	});

	it("keeps the chart visible when more than five snapshots do not overlap", () => {
		cy.visit(
			"/desk/query-report/Bond%20Yield%20Comparison?from_date=2025-04-01&to_date=2025-11-01"
		);
		cy.wait("@yieldReport");

		cy.get('.chart-wrapper [data-chart-mode="gap-aware"]').should("be.visible");
		cy.get(".chart-wrapper .chart-data-point").should("not.exist");
		cy.get(".chart-wrapper .chart-data-line").should("have.length", 6);
		cy.get(".chart-wrapper .chart-legend").should("not.exist");
		cy.get(".chart-wrapper .chart-data-line title").first().should("contain", NO_OVERLAP_BOND);
		cy.get(".chart-wrapper .chart-data-line")
			.first()
			.then(($line) => {
				const svg = $line.closest("svg")[0];
				const rect = svg.getBoundingClientRect();
				cy.wrap($line).trigger("mousemove", {
					clientX: rect.left + (rect.width * 82) / 1000,
					clientY: rect.top + rect.height / 2,
					force: true,
				});
			});
		cy.get("[data-bond-yield-hover-tooltip]").should("be.visible");
		cy.get("[data-bond-yield-hover-isin]").should("have.text", NO_OVERLAP_BOND);
		cy.get("[data-bond-yield-hover-value]").should("contain", "8.75%");
		cy.get("[data-bond-yield-hover-tooltip] [data-bond-yield-hover-isin]").should("have.length", 1);
		cy.get('[data-bond-yield-selection] .bond-yield-checkbox')
			.should("have.length", 6)
			.each(($checkbox) => cy.wrap($checkbox).should("be.checked"));
		cy.window().then((window) => {
			const chart = window.frappe.query_report.chart;
			expect(chart.data.datasets).to.have.length(6);
			expect(chart.data.datasets[0].values).to.include(null);
			expect(chart.data.datasets[0].values).to.not.include(0);
			expect(chart.legendArea).to.be.undefined;
		});
		cy.get(`[data-bond-yield-selection] input[data-bond-yield-isin="${NO_OVERLAP_BOND}"]`)
			.uncheck();
		cy.get('.chart-wrapper [data-chart-mode="gap-aware"]').should("be.visible");
		cy.window().then((window) => {
			expect(window.frappe.query_report.chart.data.datasets).to.have.length(5);
		});
	});
});

function parse_filters(filters) {
	if (!filters) {
		return {};
	}
	return typeof filters === "string" ? JSON.parse(filters) : filters;
}
