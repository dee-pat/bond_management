const MARKET_DATE = "2025-01-01";
const TARGET_ISIN = "TEST-BOND-WEIGHTED";
const REFERENCE_ISIN = "TEST-BOND-REFERENCE";
const TARGET_MARKET_PRICE = 99.25;
const TARGET_WEIGHTED_DATE = "2027-01-01";

const MARKET_DATA = {
	[TARGET_ISIN]: {
		currency: "KES",
		future_xirr: 8.75,
		principal_factor: 1,
		weighted_avg_repayment_date: TARGET_WEIGHTED_DATE,
		weighted_avg_repayment_years: 2,
	},
	[REFERENCE_ISIN]: {
		currency: "USD",
		future_xirr: 9.25,
		principal_factor: 1,
		weighted_avg_repayment_date: "2029-01-01",
		weighted_avg_repayment_years: 1461 / 365,
	},
};

const CASHFLOWS = [
	{
		isin: "=TEST\tBOND\nALERT",
		type: "+principal",
		date: TARGET_WEIGHTED_DATE,
		amount: 100,
	},
	{
		isin: TARGET_ISIN,
		type: "market_price",
		date: MARKET_DATE,
		amount: -TARGET_MARKET_PRICE,
	},
	{
		isin: TARGET_ISIN,
		type: "coupon",
		date: "2026-01-01",
		amount: 8.5,
	},
];

const EXPECTED_TSV = [
	"isin\ttransaction_type\tdate\tamount",
	`${TARGET_ISIN}\tmarket_price\t${MARKET_DATE}\t-${TARGET_MARKET_PRICE}`,
	`${TARGET_ISIN}\tcoupon\t2026-01-01\t8.5`,
	"'=TEST BOND ALERT\t'+principal\t2027-01-01\t100",
].join("\n");
const EXPECTED_COPY_MESSAGE = `Copied ${CASHFLOWS.length} cash flows for ${TARGET_ISIN}`;

context("Bond Market Date", () => {
	beforeEach(() => {
		cy.login();

		cy.intercept(
			"POST",
			"**/api/method/bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_recalculated_market_data",
			(request) => {
				const body = parse_request_body(request.body);
				const rows = typeof body.rows === "string" ? JSON.parse(body.rows) : body.rows;

				request.reply({
					statusCode: 200,
					body: {
						message: rows.map((row) => {
							const values = MARKET_DATA[row.isin];
							expect(values, `market data fixture for ${row.isin}`).to.exist;
							return { name: row.name, ...values };
						}),
					},
				});
			}
		).as("marketData");

		cy.intercept(
			"POST",
			"**/api/method/bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_cashflows",
			{
				statusCode: 200,
				body: { message: CASHFLOWS },
			}
		).as("cashflows");

		cy.visit("/desk/bond-market-date/new");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.window().should((window) => {
			expect(window.cur_frm?.doctype).to.equal("Bond Market Date");
			expect(
				window.frappe.ui.form.handlers["Bond Market Prices"]?.market_price
			).to.have.length.greaterThan(0);
		});

		cy.window().then((window) => {
			cy.stub(window.frappe.utils, "copy_to_clipboard").resolves().as("copyToClipboard");
		});

		cy.window().then((window) => {
			// Exercise the recalculation hook directly; row editing adds no useful coverage.
			const frm = window.cur_frm;
			frm.clear_table("bond_market_prices");
			frm.doc.date = MARKET_DATE;
			const target = frm.add_child("bond_market_prices", {
				isin: TARGET_ISIN,
				market_price: TARGET_MARKET_PRICE,
			});
			frm.add_child("bond_market_prices", {
				isin: REFERENCE_ISIN,
				market_price: 101,
			});
			frm.refresh_field("date");
			frm.refresh_field("bond_market_prices");

			return frm.script_manager.trigger("market_price", target.doctype, target.name);
		});
		cy.wait("@marketData");
	});

	it("copies the selected bond cash flows by clicking Future XIRR", () => {
		cy.get(`.bond-market-cashflow-copy[data-isin="${TARGET_ISIN}"]`)
			.should("be.visible")
			.as("targetXirr");
		cy.get("@targetXirr").click();

		cy.wait("@cashflows").then(({ request }) => {
			const body = parse_request_body(request.body);
			expect(body).to.include({
				date: MARKET_DATE,
				isin: TARGET_ISIN,
			});
			expect(Number(body.market_price)).to.equal(TARGET_MARKET_PRICE);
		});
		cy.get("@copyToClipboard")
			.should("have.been.calledOnce")
			.and("have.been.calledWith", EXPECTED_TSV, EXPECTED_COPY_MESSAGE);
	});

	it("renders one colored yield-curve line per currency", () => {
		cy.get(".bond-yield-curve polyline")
			.should("have.length", 2)
			.then(($lines) => {
				const currencies = [...$lines].map((line) => line.getAttribute("data-currency"));
				const colors = [...$lines].map((line) => line.getAttribute("stroke"));

				expect(currencies).to.deep.equal(["KES", "USD"]);
				expect(new Set(colors).size).to.equal(2);
			});
		cy.get('.bond-yield-legend [role="listitem"]').should("have.length", 2);
	});
});

function parse_request_body(body) {
	if (typeof body !== "string") {
		return body;
	}

	return Object.fromEntries(new URLSearchParams(body));
}
