import { expect, test } from "@playwright/test";

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
];

test("runs USD portfolio performance and copies sanitized cash flows", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/bond-investor/performance");

  await expect(
    page.getByRole("heading", { name: "Portfolio Performance" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Performance report" }),
  ).toHaveCount(0);
  await expect(page.getByTestId("performance-initial")).toBeVisible();
  await expect(page.getByLabel("Valuation Date")).not.toHaveValue("");

  await page.getByLabel("Portfolio", { exact: true }).selectOption(PORTFOLIO);
  await page.getByLabel("Valuation Date").fill(VALUATION_DATE);
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const table = page.getByTestId("performance-table");
  await expect(table).toBeVisible();
  await expect(table.getByRole("columnheader")).toHaveCount(10);
  for (const header of USD_ONLY_HEADERS) {
    await expect(
      table.getByRole("columnheader", { name: header, exact: true })
    ).toBeVisible();
  }
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

  await bondRow
    .getByRole("button", {
      name: `Copy native cash flows for ${BOND_ISIN} XIRR`,
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
    `${BOND_ISIN}\tpurchase\t${VALUATION_DATE}\tUSD\t-1051\t10\t-105.1`
  );

  await expect(
    page.getByRole("button", { name: /Export|Print|Email/ })
  ).toHaveCount(0);
  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
