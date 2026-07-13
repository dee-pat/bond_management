const MARKET_DATE = "2025-01-01";
const TARGET_ISIN = "TEST-BOND-WEIGHTED";
const REFERENCE_ISIN = "TEST-BOND-REFERENCE";
const TARGET_MARKET_PRICE = 99.25;
const TARGET_WEIGHTED_DATE = "2027-01-01";
const TARGET_MATURITY_DATE = "2032-01-01";

const MARKET_DATA = {
	[TARGET_ISIN]: {
		currency: "KES",
		future_xirr: 8.75,
		principal_factor: 1,
		weighted_avg_repayment_date: TARGET_WEIGHTED_DATE,
		weighted_avg_repayment_years: 2,
		maturity_date: TARGET_MATURITY_DATE,
	},
	[REFERENCE_ISIN]: {
		currency: "KES",
		future_xirr: 9.25,
		principal_factor: 1,
		weighted_avg_repayment_date: "2029-01-01",
		weighted_avg_repayment_years: 1461 / 365,
		maturity_date: "2029-01-01",
	},
};

const CASHFLOWS = [
	{
		isin: TARGET_ISIN,
		type: "principal",
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
	`${TARGET_ISIN}\tprincipal\t${TARGET_WEIGHTED_DATE}\t100`,
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
		cy.window().then((window) => {
			const fieldnames = window.frappe.meta
				.get_docfields("Bond Market Prices")
				.map((field) => field.fieldname);
			expect(fieldnames).not.to.include("copy_cashflows");
		});
		cy.get(
			'.frappe-control[data-fieldname="bond_market_prices"] [data-fieldname="copy_cashflows"]'
		).should("not.exist");
		cy.get(`.bond-market-cashflow-copy[data-isin="${TARGET_ISIN}"]`)
			.should("be.visible")
			.as("targetXirr");
		cy.get("@targetXirr").closest(".grid-row").should("not.have.class", "editable-row");
		cy.get("@targetXirr").click();
		cy.get("@targetXirr").closest(".grid-row").should("not.have.class", "editable-row");

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

	it("shows the ISIN on hover and positions points by weighted repayment date", () => {
		cy.get(".bond-yield-point")
			.should("have.length", 2)
			.then(($points) => {
				const points = [...$points];
				const target = find_point(points, TARGET_ISIN);
				const reference = find_point(points, REFERENCE_ISIN);

				expect(target, `${TARGET_ISIN} chart point`).to.exist;
				expect(reference, `${REFERENCE_ISIN} chart point`).to.exist;
				expect(target.getAttribute("aria-label")).to.include(TARGET_WEIGHTED_DATE);
				expect(target.getAttribute("aria-label")).not.to.include(TARGET_MATURITY_DATE);
				expect(Number(target.getAttribute("cx"))).to.be.lessThan(
					Number(reference.getAttribute("cx"))
				);

				cy.wrap(target).as("targetYieldPoint");
			});

		cy.get("@targetYieldPoint").trigger("mouseenter", { force: true });
		cy.get(".bond-yield-tooltip:visible")
			.should("contain.text", TARGET_ISIN)
			.and("contain.text", TARGET_WEIGHTED_DATE);
	});
});

function find_point(points, isin) {
	return points.find((point) => point.getAttribute("aria-label")?.includes(isin));
}

function parse_request_body(body) {
	if (typeof body !== "string") {
		return body;
	}

	return Object.fromEntries(new URLSearchParams(body));
}
