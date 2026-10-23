import { expect, test } from "@playwright/test";

import { selectFrappeOption } from "./helpers/controls";

const INVESTOR_API =
  "**/api/method/bond_management.bond_management.api.investor";
const BOND_ISIN = "UI-TEST-BOND-001";
const PORTFOLIO = "UI Test Portfolio";
const VALUATION_DATE = "2025-12-31";
const USD_ONLY_HEADERS = [
  "ISIN",
  "CCY",
  "Prin. Factor",
  "Nominal Value",
  "Purchases Value",
  "Proceeds Value",
  "Market Value",
  "Gain Value",
  "XIRR",
  "Future XIRR",
  "Next Coupon Date",
  "Next Coupon Amount",
  "Second Coupon Date",
  "Second Coupon Amount",
];

test("copies past cash flows without XIRR and future cash flows", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/bond-investor/performance");

  await expect(
    page.getByRole("heading", { name: "Portfolio Performance" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Performance report" })
  ).toHaveCount(0);
  await expect(page.getByTestId("performance-initial")).toBeVisible();
  await expect(page.getByLabel("Valuation Date")).not.toHaveValue("");

  await selectFrappeOption(page, "Portfolio (required)", PORTFOLIO);
  await page.getByLabel("Valuation Date").fill(VALUATION_DATE);
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const table = page.getByTestId("performance-table");
  await expect(table).toBeVisible();
  const headers = table.getByRole("columnheader");
  await expect(headers).toHaveCount(14);
  expect(
    await headers.evaluateAll((elements) =>
      elements.map((element) => element.textContent?.trim() ?? "")
    )
  ).toEqual(USD_ONLY_HEADERS);
  const rows = table.getByRole("row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(1).getByRole("cell")).toHaveCount(14);
  await expect(
    table.getByRole("columnheader", { name: "Market Value (USD)", exact: true })
  ).toHaveCount(0);
  await expect(
    table.getByRole("columnheader", { name: "XIRR (USD)", exact: true })
  ).toHaveCount(0);

  const bondRow = page
    .getByTestId("performance-row")
    .filter({ hasText: BOND_ISIN });
  await expect(bondRow).toContainText("USD");
  await expect(bondRow).toContainText("1.000");
  await expect(bondRow).toContainText("1,000.00");
  await expect(bondRow).toContainText("1,051.00");
  await expect(bondRow).toContainText("01 Jan 2026");
  await expect(bondRow).toContainText("01 Jul 2026");
  await expect(bondRow.getByRole("cell").nth(11)).toContainText("35.00");
  await expect(bondRow.getByRole("cell").nth(13)).toContainText("35.00");
  await expect(bondRow).toContainText("1,059.81");
  await expect(bondRow).toContainText("8.81");
  await expect(bondRow).toContainText("4.473%");
  await expect(
    bondRow.getByRole("link", { name: `View bond ${BOND_ISIN}` })
  ).toHaveAttribute("href", `/bond-investor/bonds/${BOND_ISIN}`);

  const totalRow = page
    .getByTestId("performance-row")
    .filter({ hasText: "TOTAL" });
  await expect(totalRow).toContainText("1,059.81");
  await expect(totalRow).toContainText("4.473%");

  const pastCopy = bondRow.getByRole("button", {
    name: `Copy native cash flows for ${BOND_ISIN} XIRR`,
    exact: true,
  });
  await expect(pastCopy).toHaveText("Copy cash flows");
  await expect(
    totalRow.getByRole("button", {
      name: "Copy native cash flows for TOTAL XIRR",
      exact: true,
    })
  ).toHaveText("Copy cash flows");
  await pastCopy.click();
  await expect(page.getByRole("status")).toContainText(
    /^Copied \d+ cash flows\.$/
  );
  const pastClipboard = await page.evaluate(() =>
    navigator.clipboard.readText()
  );
  expect(pastClipboard).toContain(
    `${BOND_ISIN}\tpurchase\t${VALUATION_DATE}\tUSD\t-1051`
  );

  await bondRow
    .getByRole("button", {
      name: `Copy native cash flows for ${BOND_ISIN} Future XIRR`,
      exact: true,
    })
    .click();
  await expect(page.getByRole("status")).toContainText(
    /^Copied \d+ cash flows\.$/
  );
  const clipboard = await page.evaluate(() => navigator.clipboard.readText());
  expect(clipboard).toContain(
    "isin\ttransaction_type\tdate\tcurrency\tamount\tquantity\trate"
  );
  expect(clipboard).toContain(
    `${BOND_ISIN}\tmarket_price\t${VALUATION_DATE}\tUSD\t-1025\t10\t-102.5`
  );

  await expect(
    page.getByRole("button", { name: /Export|Print|Email/ })
  ).toHaveCount(0);
  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});

test("shows a failure instead of the previous report when a rerun cannot connect", async ({
  page,
}) => {
  let attempts = 0;
  await page.route(
    `${INVESTOR_API}.get_portfolio_performance?*`,
    async (route) => {
      attempts += 1;
      if (attempts !== 2) {
        await route.continue();
        return;
      }
      await route.abort("failed");
    }
  );

  await page.goto("/bond-investor/performance");
  await selectFrappeOption(page, "Portfolio (required)", PORTFOLIO);
  await page.getByLabel("Valuation Date").fill(VALUATION_DATE);
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByTestId("performance-table")).toBeVisible();

  await page.getByLabel("Valuation Date").fill("2026-01-30");
  await page.getByRole("button", { name: "Run", exact: true }).click();

  await expect(page.getByRole("alert")).toContainText(
    "Portfolio performance could not be loaded"
  );
  await expect(page.getByTestId("performance-table")).toHaveCount(0);
  expect(attempts).toBe(2);

  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByTestId("performance-table")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(attempts).toBe(3);
});
