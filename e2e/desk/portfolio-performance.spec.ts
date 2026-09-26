import { expect, test } from "@playwright/test";

import { installPortfolioPerformanceFixtures } from "./fixtures";
import { captureClipboard, readClipboardCalls } from "./helpers/frappe";

const reportRoute =
  "/desk/query-report/Portfolio%20Performance?portfolio=TEST-PORTFOLIO&valuation_date=2025-12-31";
const cashflowMethod =
  "bond_management.bond_management.report.portfolio_performance.portfolio_performance.get_xirr_cashflows";

test("copies cash flows from the rendered XIRR action", async ({ page }) => {
  await installPortfolioPerformanceFixtures(page, "copy-cashflows");
  await page.goto(reportRoute);
  await expect(
    page.locator(".dt-row-0 .dt-cell--col-2 .dt-cell__content")
  ).toContainText("12.500%");

  await expect(
    page.locator(".dt-row-0 .dt-cell--col-3 .dt-cell__content")
  ).toContainText("8.750%");
  await expect(
    page.locator(".dt-row-0 .dt-cell--col-4 .dt-cell__content")
  ).toContainText("7.250%");
  await expect(
    page.getByText("Expected Coupons (Next Year)", { exact: true })
  ).toBeVisible();
  const couponRow = page.locator(".dt-row").filter({ hasText: "TEST-BOND" });
  await expect(couponRow).toHaveCount(1);
  await expect(couponRow).toContainText("70.00");
  const undefinedYieldActions = page.locator(
    '.portfolio-cashflow-copy[data-isin="UNDEFINED-XIRR"]'
  );
  await expect(undefinedYieldActions).toHaveCount(3);
  await expect(undefinedYieldActions).toHaveText([
    "Copy cash flows",
    "Copy cash flows",
    "Copy cash flows",
  ]);
  await expect(
    page.locator(
      '.portfolio-cashflow-copy[data-isin="CLOSED-BOND"][data-xirr-type="future"]'
    )
  ).toHaveCount(0);
  await expect(
    page.locator(
      '.portfolio-cashflow-copy[data-isin="CLOSED-BOND"][data-xirr-type="past"][data-cashflow-currency="native"]'
    )
  ).toContainText("0.000%");
  await expect(
    page.locator(
      '.portfolio-cashflow-copy[data-isin="TOTAL"][data-cashflow-currency="native"]'
    )
  ).toHaveCount(0);

  await captureClipboard(page);
  const copyAction = page.locator(
    '.portfolio-cashflow-copy[data-isin="UNDEFINED-XIRR"][data-xirr-type="past"][data-cashflow-currency="reporting"]'
  );
  await expect(copyAction).toBeVisible();
  const cashflowResponse = page.waitForResponse((response) =>
    response.url().includes(cashflowMethod)
  );
  await copyAction.click();
  const request = await cashflowResponse;
  const requestData = parsePostData(request.request().postData());

  expect(requestData).toMatchObject({
    portfolio: "TEST-PORTFOLIO",
    valuation_date: "2025-12-31",
    isin: "UNDEFINED-XIRR",
    xirr_type: "past",
    cashflow_currency: "reporting",
  });
  expect(await readClipboardCalls(page)).toEqual([
    [
      "isin\ttransaction_type\tdate\tcurrency\tamount\tquantity\trate\n'=TEST BOND ALERT\t'+purchase\t2025-12-31\t'@USD\t-1000\t10\t-100",
      "Copied 1 cash flows",
    ],
  ]);
});

test("hides duplicate USD columns for a USD-only portfolio", async ({
  page,
}) => {
  await installPortfolioPerformanceFixtures(page, "usd-only");
  await page.goto(reportRoute);

  await expect(
    page.getByText("Expected Coupons (Next Year)", { exact: true })
  ).toBeVisible();
  const headers = await page
    .locator(".dt-cell--header .dt-cell__content")
    .allTextContents();
  expect(headers.join(" ")).not.toContain("Market Value (USD)");
  expect(headers.join(" ")).not.toContain("XIRR (USD)");
});

function parsePostData(postData: string | null): Record<string, string> {
  return Object.fromEntries(new URLSearchParams(postData ?? ""));
}
