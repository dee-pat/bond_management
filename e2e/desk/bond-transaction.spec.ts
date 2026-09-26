import { expect, test } from "@playwright/test";

import { openDeskForm, type DeskTestWindow } from "./helpers/frappe";

const singleTransaction = {
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

const calculatedAmounts = {
  principal: 20000,
  commission_amount: 90,
  settlement_amount: 44132.5,
  transaction_amount: 44042.5,
  accrued_interest_calculated: 24062.5,
};

const transactionCalculationMethod =
  "bond_management.bond_management.doctype.bond_transaction.bond_transaction.get_calculated_amounts";

test("populates and locks one PDF transaction, then unlocks manual entry", async ({
  page,
}) => {
  await openDeskForm(page, "/desk/bond-transaction/new", "Bond Transaction");

  const handlerExists = await page.evaluate(() => {
    const handlers = (window as DeskTestWindow).frappe.ui.form.handlers[
      "Bond Transaction"
    ]?.attachment;
    return Array.isArray(handlers) && handlers.length > 0;
  });
  expect(handlerExists).toBe(true);

  await page.evaluate(
    async ({ transaction, calculationMethod, amounts }) => {
      const testWindow = window as DeskTestWindow;
      const form = testWindow.cur_frm;
      if (!form) {
        throw new Error("Bond Transaction form did not load");
      }

      testWindow.__testCalls = {};
      const originalFormCall = form.call.bind(form);
      form.call = async (...args) => {
        if (args[0] === "read_transaction_pdf") {
          testWindow.__testCalls!.readTransactionPdf =
            (testWindow.__testCalls!.readTransactionPdf ?? 0) + 1;
          return { message: { transactions: [transaction] } };
        }
        return originalFormCall(...args);
      };

      const originalFrappeCall = testWindow.frappe.call.bind(testWindow.frappe);
      testWindow.frappe.call = async (options) => {
        if (options.method === calculationMethod) {
          return { message: amounts };
        }
        return originalFrappeCall(options);
      };

      form.doc.attachment = "/private/files/transaction.pdf";
      form.refresh_field("attachment");
      await form.script_manager.trigger("attachment");
    },
    {
      transaction: singleTransaction,
      calculationMethod: transactionCalculationMethod,
      amounts: calculatedAmounts,
    }
  );

  const populated = await page.evaluate(() => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Transaction form did not load");
    }

    const fieldOrder = form.fields.map((field) => field.df.fieldname);
    const rightColumnFields = fieldOrder.slice(
      fieldOrder.indexOf("column_break_jo9c") + 1
    );
    return {
      readCount: (window as DeskTestWindow).__testCalls?.readTransactionPdf,
      transactionReference: form.doc.transaction_reference,
      transactionType: form.doc.transaction_type,
      portfolioName: form.doc.portfolio_name,
      quantity: form.doc.quantity_face_value,
      transactionAmount: form.doc.transaction_amount,
      amountDescription: form.get_field("transaction_amount").df.description,
      rightColumnFields,
      priceReadOnly: form.get_field("price").df.read_only,
      referenceReadOnly: form.get_field("transaction_reference").df.read_only,
    };
  });

  expect(populated.readCount).toBe(1);
  expect(populated.transactionReference).toBe(
    singleTransaction.transaction_reference
  );
  expect(populated.transactionType).toBe(singleTransaction.transaction_type);
  expect(populated.portfolioName).toBe(singleTransaction.portfolio_name);
  expect(populated.quantity).toBe(singleTransaction.quantity_face_value);
  expect(populated.transactionAmount).toBe(
    calculatedAmounts.transaction_amount
  );
  expect(populated.amountDescription).toContain(
    "Settlement Amount less Commission Amount"
  );
  expect(populated.rightColumnFields).toEqual(
    expect.arrayContaining([
      "commission_amount",
      "settlement_amount",
      "transaction_amount",
    ])
  );
  expect(populated.priceReadOnly).toBe(1);
  expect(populated.referenceReadOnly).toBe(1);

  const unlocked = await page.evaluate(async () => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Transaction form did not load");
    }

    form.doc.attachment = null;
    form.refresh_field("attachment");
    await form.script_manager.trigger("attachment");
    return {
      priceReadOnly: form.get_field("price").df.read_only,
      referenceReadOnly: form.get_field("transaction_reference").df.read_only,
      transactionReference: form.doc.transaction_reference,
    };
  });

  expect(unlocked.priceReadOnly).toBe(0);
  expect(unlocked.referenceReadOnly).toBe(0);
  expect(unlocked.transactionReference).toBe(
    singleTransaction.transaction_reference
  );
});
