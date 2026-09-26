import { expect, test } from "@playwright/test";

import { openDeskForm, type DeskTestWindow } from "./helpers/frappe";

const statement = {
  portfolio_name: "Nanda",
  statement_date: "2026-06-30",
  account_no: "1110700431102",
};

test("reads the portfolio and date when a PDF is attached", async ({
  page,
}) => {
  await openDeskForm(page, "/desk/bond-statement/new", "Bond Statement");

  const initialFields = await page.evaluate(() => {
    const testWindow = window as DeskTestWindow;
    const form = testWindow.cur_frm;
    if (!form) {
      throw new Error("Bond Statement form did not load");
    }
    const attachmentHandlers =
      testWindow.frappe.ui.form.handlers["Bond Statement"]?.attachment;
    return {
      hasAttachmentHandler:
        Array.isArray(attachmentHandlers) && attachmentHandlers.length > 0,
      portfolioReadOnly: form.get_field("portfolio_name").df.read_only,
      statementDateReadOnly: form.get_field("statement_date").df.read_only,
      postingReadOnly: form.get_field("market_price_posting").df.read_only,
    };
  });

  expect(initialFields.hasAttachmentHandler).toBe(true);
  expect(initialFields.portfolioReadOnly).toBe(0);
  expect(initialFields.statementDateReadOnly).toBe(1);
  expect(initialFields.postingReadOnly).toBe(1);

  await page.evaluate(async (statementData) => {
    const testWindow = window as DeskTestWindow;
    const form = testWindow.cur_frm;
    if (!form) {
      throw new Error("Bond Statement form did not load");
    }

    testWindow.__testCalls = {};
    const originalCall = form.call.bind(form);
    form.call = async (...args) => {
      if (args[0] === "read_statement_pdf") {
        testWindow.__testCalls!.readStatementPdf =
          (testWindow.__testCalls!.readStatementPdf ?? 0) + 1;
        return { message: statementData };
      }
      return originalCall(...args);
    };

    form.doc.attachment = "/private/files/statement.pdf";
    form.refresh_field("attachment");
    await form.script_manager.trigger("attachment");
  }, statement);

  const result = await page.evaluate(() => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Statement form did not load");
    }
    return {
      callCount: (window as DeskTestWindow).__testCalls?.readStatementPdf,
      portfolioName: form.doc.portfolio_name,
      statementDate: form.doc.statement_date,
      portfolioReadOnly: form.get_field("portfolio_name").df.read_only,
    };
  });

  expect(result.callCount).toBe(1);
  expect(result.portfolioName).toBe(statement.portfolio_name);
  expect(result.statementDate).toBe(statement.statement_date);
  expect(result.portfolioReadOnly).toBe(1);
});
