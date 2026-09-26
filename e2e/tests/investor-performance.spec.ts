import { expect, test } from "@playwright/test";

import { selectFrappeOption } from "../support/controls";

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
  "Expected Coupons (Next Year)",
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
  await expect(headers).toHaveCount(11);
  expect(
    await headers.evaluateAll((elements) =>
      elements.map((element) => element.textContent?.trim() ?? "")
    )
  ).toEqual(USD_ONLY_HEADERS);
  await expect(table.locator("tbody > tr")).toHaveCount(2);
  await expect(table.locator("tbody > tr").first().locator("td")).toHaveCount(11);
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
  await expect(bondRow).toContainText("70.00");
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
