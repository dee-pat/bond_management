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
		cy.window().then((window) => {
			// Invoke the attachment hook deterministically instead of uploading a fixture.
			const frm = window.cur_frm;
			stub_transaction_calculation(window);
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
});

function stub_transaction_calculation(window) {
	const original_frappe_call = window.frappe.call.bind(window.frappe);
	cy.stub(window.frappe, "call").callsFake((options) => {
		if (options?.method === TRANSACTION_CALCULATION_METHOD) {
			return Promise.resolve({ message: CALCULATED_AMOUNTS });
		}
		return original_frappe_call(options);
	});
}
