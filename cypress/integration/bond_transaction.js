const SINGLE_TRANSACTION = {
	transaction_reference: "U2000001",
	transaction_type: "Purchase",
	isin: "XS3196101201",
	portfolio_name: "Dhanbai",
	trade_date: "2026-06-02",
	settlement_date: "2026-06-03",
	quantity_face_value: 20000,
	price: 100.35,
	accrued_interest_paid: 24062.5,
	commission: 0.45,
};

const CALCULATED_AMOUNTS = {
	principal: 20000,
	commission_amount: 90,
	settlement_amount: 44132.5,
	accrued_interest_calculated: 24062.5,
};

const TRANSACTION_CALCULATION_METHOD =
	"bond_management.bond_management.doctype.bond_transaction.bond_transaction.get_calculated_amounts";

context("Bond Transaction PDF entry", () => {
	beforeEach(() => {
		cy.login();
		cy.visit("/desk/bond-transaction/new");
		cy.get("body").should("have.attr", "data-ajax-state", "complete");
		cy.window().should((window) => {
			expect(window.cur_frm?.doctype).to.equal("Bond Transaction");
			expect(
				window.frappe.ui.form.handlers["Bond Transaction"]?.attachment
			).to.have.length.greaterThan(0);
		});
	});

	it("populates and locks a single PDF transaction, then unlocks manual entry", () => {
		cy.get('.frappe-control[data-fieldname="attachment"] .attached-file')
			.should("have.css", "min-height", "56px")
			.find(".attached-file-link")
			.should("have.css", "white-space", "normal")
			.and("have.css", "overflow-wrap", "anywhere");

		cy.window().then((window) => {
			const frm = window.cur_frm;
			const original_frappe_call = window.frappe.call.bind(window.frappe);
			cy.stub(window.frappe, "call").callsFake((options) => {
				if (options?.method === TRANSACTION_CALCULATION_METHOD) {
					return Promise.resolve({ message: CALCULATED_AMOUNTS });
				}
				return original_frappe_call(options);
			});
			cy.stub(frm, "call")
				.withArgs("read_transaction_pdf")
				.resolves({ message: { transactions: [SINGLE_TRANSACTION] } })
				.as("readTransactionPdf");

			frm.doc.attachment = "/private/files/transaction.pdf";
			frm.refresh_field("attachment");
			return frm.script_manager.trigger("attachment");
		});

		cy.get("@readTransactionPdf").should("have.been.calledOnce");
		cy.window().then((window) => {
			const frm = window.cur_frm;
			expect(frm.doc.transaction_reference).to.equal("U2000001");
			expect(frm.doc.transaction_type).to.equal("Purchase");
			expect(frm.doc.portfolio_name).to.equal("Dhanbai");
			expect(frm.doc.quantity_face_value).to.equal(20000);
			expect(frm.get_field("price").df.read_only).to.equal(1);
			expect(frm.get_field("transaction_reference").df.read_only).to.equal(1);

			frm.doc.attachment = null;
			frm.refresh_field("attachment");
			return frm.script_manager.trigger("attachment");
		});

		cy.window().then((window) => {
			const frm = window.cur_frm;
			expect(frm.get_field("price").df.read_only).to.equal(0);
			expect(frm.get_field("transaction_reference").df.read_only).to.equal(0);
			expect(frm.doc.transaction_reference).to.equal("U2000001");
		});
	});

	it("selects every row by default and posts multiple documents", () => {
		const transactions = [
			SINGLE_TRANSACTION,
			{
				...SINGLE_TRANSACTION,
				transaction_reference: "U2000002",
				quantity_face_value: 10000,
			},
		];

		cy.window().then((window) => {
			const frm = window.cur_frm;
			cy.stub(window.frappe, "set_route").resolves().as("setRoute");
			cy.stub(frm, "call")
				.callsFake((method, args) => {
					if (method === "read_transaction_pdf") {
						return Promise.resolve({ message: { transactions } });
					}
					if (method === "create_selected_pdf_transactions") {
						expect(args.transaction_selections).to.deep.equal([
							{ transaction_reference: "U2000001", portfolio_name: "Dhanbai" },
							{ transaction_reference: "U2000002", portfolio_name: "Dhanbai" },
						]);
						return Promise.resolve({ message: ["U2000001", "U2000002"] });
					}
					throw new Error(`Unexpected form call: ${method}`);
				})
				.as("transactionPdfCall");

			frm.doc.attachment = "/private/files/multi-transaction.pdf";
			frm.refresh_field("attachment");
			return frm.script_manager.trigger("attachment");
		});

		cy.get(
			'.modal:visible [data-fieldname="transactions"] .grid-body [data-fieldname="post"] input:checkbox'
		)
			.should("have.length", 2)
			.each(($checkbox) => {
				expect($checkbox).to.have.class("disabled-selected");
			});
		cy.get(".modal:visible .modal-footer .btn-primary").click();

		cy.get("@transactionPdfCall").should("have.been.calledTwice");
		cy.get("@setRoute").should("have.been.calledOnce");
	});
});
