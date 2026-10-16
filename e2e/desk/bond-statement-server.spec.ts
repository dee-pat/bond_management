import { expect, test, type Page } from "@playwright/test";

import { openDeskForm, type DeskTestWindow } from "./helpers/frappe";
import { buildTextPdf } from "./helpers/pdf";

// Seeded by `tests/investor_ui_seed.py`: a Desk-only portfolio with no
// transactions, so the generated reconciliation report is always "Matched".
const portfolioName = "UI Desk Smoke Portfolio";
const accountNo = "UI-DESK-SMOKE-001";
const statementDate = "2026-06-30";

const statementPdfLines = (account: string) => [
  "Portfolio Summary as of 30/06/2026",
  `Product Account No.: ${account}`,
];

interface FileRow {
  file_url: string;
  is_private: number;
  attached_to_field: string;
}

async function deleteSmokeStatements(page: Page): Promise<void> {
  await page.evaluate(async (portfolio) => {
    const { frappe } = window as DeskTestWindow;
    const { message } = await frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Bond Statement",
        filters: { portfolio_name: portfolio },
        fields: ["name"],
      },
    });
    for (const { name } of (message as Array<{ name: string }>) ?? []) {
      await frappe.call({
        method: "frappe.client.delete",
        args: { doctype: "Bond Statement", name },
      });
    }
  }, portfolioName);
}

async function attachPdf(page: Page, fileName: string, account: string) {
  await page
    .locator('[data-fieldname="attachment"]')
    .getByRole("button", { name: "Attach", exact: true })
    .click();
  const dialog = page.getByRole("dialog").filter({ hasText: "Upload" });
  await dialog.locator('input[type="file"]').setInputFiles({
    name: fileName,
    mimeType: "application/pdf",
    buffer: buildTextPdf(statementPdfLines(account)),
  });
  await expect(dialog.getByRole("checkbox", { name: "Private" })).toBeChecked();
  await dialog.getByRole("button", { name: "Upload", exact: true }).click();
}

function readForm(page: Page) {
  return page.evaluate(() => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Statement form did not load");
    }
    return {
      name: String(form.doc.name),
      attachment: form.doc.attachment as string | undefined,
      portfolioName: form.doc.portfolio_name as string | undefined,
      statementDate: form.doc.statement_date as string | undefined,
      reconciliationStatus: form.doc.reconciliation_status as string | undefined,
      report: form.doc.quantity_reconciliation_report as string | undefined,
      portfolioReadOnly: form.get_field("portfolio_name").df.read_only,
      isDirty: form.is_dirty(),
    };
  });
}

test.beforeEach(async ({ page }) => {
  await openDeskForm(page, "/desk/bond-statement/new", "Bond Statement");
  await deleteSmokeStatements(page);
  await openDeskForm(page, "/desk/bond-statement/new", "Bond Statement");
});

test("uploads, parses and saves a statement PDF with its private report", async ({
  page,
}) => {
  await test.step("a rejected PDF leaves the form recoverable", async () => {
    await attachPdf(page, "unknown-account.pdf", "UI-DESK-UNKNOWN-999");

    const error = page
      .getByRole("dialog")
      .filter({ hasText: "No accessible Bond Portfolio has account number" });
    await expect(error).toBeVisible();
    await error.getByRole("button", { name: "Close" }).click();

    const form = await readForm(page);
    expect(form.portfolioName).toBeFalsy();
    expect(form.statementDate).toBeFalsy();
    expect(form.portfolioReadOnly).toBe(0);

    await page
      .locator('[data-fieldname="attachment"]')
      .getByText("Clear", { exact: true })
      .click();
    await page
      .getByRole("dialog")
      .filter({ hasText: "Are you sure you want to delete the attachment?" })
      .getByRole("button", { name: "Yes" })
      .click();
    await expect
      .poll(async () => (await readForm(page)).attachment)
      .toBeFalsy();
  });

  await test.step("the server reads the portfolio and date", async () => {
    await attachPdf(page, "smoke-statement.pdf", accountNo);

    await expect
      .poll(async () => (await readForm(page)).portfolioName)
      .toBe(portfolioName);
    const form = await readForm(page);
    expect(form.statementDate).toBe(statementDate);
    expect(form.portfolioReadOnly).toBe(1);
  });

  await test.step("save stores server-authoritative values", async () => {
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page).toHaveURL(/\/bond-statement\/BS-\d+$/);
    await expect.poll(async () => (await readForm(page)).isDirty).toBe(false);

    const form = await readForm(page);
    expect(form.portfolioName).toBe(portfolioName);
    expect(form.statementDate).toBe(statementDate);
    expect(form.reconciliationStatus).toBe("Matched");
    expect(form.attachment).toMatch(
      new RegExp(`^/private/files/PortfolioStatement-${accountNo}-20260630`)
    );
    expect(form.report).toMatch(
      new RegExp(`^/private/files/Bond-Quantity-Reconciliation-${form.name}`)
    );
  });

  await test.step("the owning record lists both private files", async () => {
    const form = await readForm(page);
    const files = await page.evaluate(async (statementName) => {
      const { message } = await (window as DeskTestWindow).frappe.call({
        method: "frappe.client.get_list",
        args: {
          doctype: "File",
          filters: {
            attached_to_doctype: "Bond Statement",
            attached_to_name: statementName,
          },
          fields: ["file_url", "is_private", "attached_to_field"],
        },
      });
      return message as FileRow[];
    }, form.name);

    expect(files).toEqual(
      expect.arrayContaining([
        { file_url: form.attachment, is_private: 1, attached_to_field: "attachment" },
        {
          file_url: form.report,
          is_private: 1,
          attached_to_field: "quantity_reconciliation_report",
        },
      ])
    );

    const report = await page.request.get(form.report!);
    expect(report.status()).toBe(200);
    expect((await report.body()).subarray(0, 5).toString("latin1")).toBe("%PDF-");
  });
});
