import { expect, test } from "@playwright/test";

const reportRoute =
  "/desk/query-report/Interest%20Difference%20by%20Portfolio?portfolio_name=UI%20Test%20Portfolio";

test("requires a portfolio first and shows equivalent interest days", async ({
  page,
}) => {
  await page.route(
    "**/api/method/frappe.desk.search.search_link*",
    async (route) => {
      await route.fulfill({
        json: {
          message: [
            { value: "UI Test Portfolio", description: "Test portfolio" },
          ],
        },
      });
    },
  );
  await page.route(
    "**/api/method/frappe.client.validate_link_and_fetch*",
    async (route) => {
      await route.fulfill({ json: { message: { name: "UI Test Portfolio" } } });
    },
  );
  await page.route(
    "**/api/method/frappe.desk.query_report.run*",
    async (route) => {
      await route.fulfill({
        json: {
          message: {
            columns: [
              {
                label: "Transaction Reference",
                fieldname: "transaction_reference",
                fieldtype: "Data",
              },
              {
                label: "Settlement Date",
                fieldname: "settlement_date",
                fieldtype: "Date",
              },
              { label: "Currency", fieldname: "currency", fieldtype: "Data" },
              {
                label: "ISIN",
                fieldname: "isin",
                fieldtype: "Link",
                options: "Bond Master",
              },
              {
                label: "Type",
                fieldname: "transaction_type",
                fieldtype: "Data",
              },
              {
                label: "Interest Calculated",
                fieldname: "accrued_interest_calculated",
                fieldtype: "Currency",
                options: "currency",
              },
              {
                label: "Interest Charged",
                fieldname: "accrued_interest_paid",
                fieldtype: "Currency",
                options: "currency",
              },
              {
                label: "Investor Gain + / Loss -",
                fieldname: "interest_difference",
                fieldtype: "Currency",
                options: "currency",
              },
              {
                label: "Difference (Days, DCC)",
                fieldname: "interest_difference_days",
                fieldtype: "Float",
              },
            ],
            result: [],
            execution_time: 0.01,
          },
        },
      });
    },
  );

  await page.goto(reportRoute);
  const portfolioFilter = page.locator(
    '.page-form .form-group[data-fieldname="portfolio_name"]',
  );
  await expect(portfolioFilter).toBeVisible();
  await expect(portfolioFilter.locator(".reqd")).toBeVisible();

  const filterOrder = await page
    .locator(".page-form .form-group[data-fieldname]")
    .evaluateAll((filters) =>
      filters.map((filter) => filter.getAttribute("data-fieldname")),
    );
  expect(filterOrder[0]).toBe("portfolio_name");

  const headers = await page
    .locator(".dt-cell--header .dt-cell__content")
    .allTextContents();
  expect(headers).toContain("Difference (Days, DCC)");
  expect(headers).not.toContain("Portfolio");
});
