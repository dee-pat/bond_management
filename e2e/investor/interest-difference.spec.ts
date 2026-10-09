import { expect, test } from "@playwright/test";

import { selectFrappeOption } from "./helpers/controls";

const PORTFOLIO = "UI Test Portfolio";

test("submits the latest dates when replacing an existing range", async ({
  page,
}) => {
  let requestedFilters: Record<string, unknown> | undefined;
  const report = {
    filters: { portfolio: PORTFOLIO, from_date: null, to_date: null },
    columns: [],
    rows: [],
    chart: null,
  };

  await page.route(
    "**/api/method/bond_management.bond_management.api.investor.get_interest_difference_by_portfolio*",
    async (route) => {
      const params = new URL(route.request().url()).searchParams;
      requestedFilters = {
        portfolio: params.get("portfolio"),
        from_date: params.get("from_date"),
        to_date: params.get("to_date"),
      };
      await route.fulfill({
        json: { message: { report }, data: { report } },
      });
    },
  );

  await page.goto("/bond-investor/interest-difference");
  await selectFrappeOption(page, "Portfolio (required)", PORTFOLIO);

  const fromDate = page.getByLabel("From Settlement Date");
  const toDate = page.getByLabel("To Settlement Date");
  await fromDate.fill("2025-01-01");
  await toDate.fill("2025-02-01");
  await fromDate.fill("2025-03-01");
  await toDate.fill("2025-04-01");

  const runButton = page.getByRole("button", { name: "Run", exact: true });
  await expect(runButton).toBeEnabled();
  await runButton.click();

  await expect(page.getByTestId("interest-difference-empty")).toBeVisible();
  expect(requestedFilters).toMatchObject({
    portfolio: PORTFOLIO,
    from_date: "2025-03-01",
    to_date: "2025-04-01",
  });
});

test("runs interest difference for the selected portfolio", async ({
  page,
}) => {
  await page.goto("/bond-investor/interest-difference");

  await expect(
    page.getByRole("heading", { name: "Interest Difference" }),
  ).toBeVisible();
  await expect(page.getByTestId("interest-difference-initial")).toBeVisible();
  await selectFrappeOption(page, "Portfolio (required)", PORTFOLIO);
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const table = page.getByTestId("interest-difference-table");
  await expect(table).toBeVisible();
  const headers = table.getByRole("columnheader");
  await expect(headers).toHaveCount(9);
  const headerLabels = await headers.evaluateAll((elements) =>
    elements.map((element) => element.textContent?.trim() ?? ""),
  );
  expect(headerLabels).toContain("Difference (Days, DCC)");
  expect(headerLabels).toContain("Investor Gain + / Loss -");
  expect(headerLabels).not.toContain("Portfolio");
  expect(headerLabels).not.toContain("Transactions");
  await expect(
    page.getByTestId("interest-difference-row").first(),
  ).toBeVisible();
  await expect(page.getByTestId("interest-difference-total-row")).toBeVisible();
});

test("identifies total rows with a marker instead of their display label", async ({
  page,
}) => {
  const report = {
    filters: { portfolio: PORTFOLIO, from_date: null, to_date: null },
    columns: [
      { fieldname: "transaction_reference", label: "Reference", fieldtype: "Data" },
      { fieldname: "settlement_date", label: "Settlement Date", fieldtype: "Date" },
      { fieldname: "currency", label: "Currency", fieldtype: "Data" },
      { fieldname: "isin", label: "ISIN", fieldtype: "Link", options: "Bond Master" },
      { fieldname: "transaction_type", label: "Type", fieldtype: "Data" },
      { fieldname: "accrued_interest_calculated", label: "Calculated", fieldtype: "Currency" },
      { fieldname: "accrued_interest_paid", label: "Charged", fieldtype: "Currency" },
      { fieldname: "interest_difference", label: "Difference", fieldtype: "Currency" },
      { fieldname: "interest_difference_days", label: "Days", fieldtype: "Float" },
    ],
    rows: [
      {
        transaction_reference: "Total",
        settlement_date: null,
        currency: "USD",
        isin: null,
        transaction_type: null,
        accrued_interest_calculated: 8,
        accrued_interest_paid: 10,
        interest_difference: -2,
        interest_difference_days: -1.25,
        is_total_row: false,
      },
      {
        transaction_reference: "Jumla",
        settlement_date: null,
        currency: "USD",
        isin: null,
        transaction_type: null,
        accrued_interest_calculated: 8,
        accrued_interest_paid: 10,
        interest_difference: -2,
        interest_difference_days: null,
        is_total_row: true,
      },
    ],
    chart: null,
  };

  await page.route(
    "**/api/method/bond_management.bond_management.api.investor.get_interest_difference_by_portfolio*",
    async (route) => {
      await route.fulfill({
        json: {
          message: { report },
          data: { report },
        },
      });
    },
  );

  await page.goto("/bond-investor/interest-difference");
  await selectFrappeOption(page, "Portfolio (required)", PORTFOLIO);
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const detailRow = page.getByTestId("interest-difference-row");
  await expect(detailRow).toHaveCount(1);
  await expect(detailRow).toContainText("Total");
  const totalRow = page.getByTestId("interest-difference-total-row");
  await expect(totalRow).toHaveCount(1);
  await expect(totalRow).toContainText("Jumla");
});
