import { expect, test } from "@playwright/test";

const reportRoute =
  "/desk/query-report/Interest%20Difference%20by%20Portfolio?portfolio_name=UI%20Test%20Portfolio";

test("shows the portfolio first and equivalent interest days", async ({
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
            result: [
              {
                transaction_reference: "TEST-INTEREST-001",
                settlement_date: "2025-01-02",
                currency: "USD",
                isin: "TEST-BOND-001",
                transaction_type: "Purchase",
                accrued_interest_calculated: 8,
                accrued_interest_paid: 10,
                interest_difference: -2,
                interest_difference_days: -1.25,
              },
              {
                transaction_reference: "Total",
                currency: "USD",
                accrued_interest_calculated: 8,
                accrued_interest_paid: 10,
                interest_difference: -2,
                interest_difference_days: null,
                is_total_row: 1,
              },
            ],
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
  await expect(
    portfolioFilter.getByRole("combobox", { name: "Portfolio" }),
  ).toBeVisible();

  const filterOrder = await page
    .locator(".page-form .form-group[data-fieldname]")
    .evaluateAll((filters) =>
      filters.map((filter) => filter.getAttribute("data-fieldname")),
    );
  expect(filterOrder[0]).toBe("portfolio_name");

  const headers = page.locator(".dt-cell--header");
  await expect(
    headers.filter({ hasText: "Difference (Days, DCC)" }),
  ).toHaveCount(1);
  await expect(headers.filter({ hasText: "Portfolio" })).toHaveCount(0);
  await expect(headers.filter({ hasText: "Transactions" })).toHaveCount(0);
});
