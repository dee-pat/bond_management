import { expect, test } from "@playwright/test";

const BOND_ISIN = "UI-TEST-BOND-001";
const PORTFOLIO = "UI Test Portfolio";
const VALUATION_DATE = "2025-12-31";

test("runs portfolio performance without mobile overflow", async ({ page }) => {
  await page.goto("/bond-investor/performance");

  await expect(page.getByTestId("performance-initial")).toBeVisible();
  await page.getByLabel("Portfolio", { exact: true }).selectOption(PORTFOLIO);
  await page.getByLabel("Valuation Date").fill(VALUATION_DATE);
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const table = page.getByTestId("performance-table");
  await expect(table).toBeVisible();
  await expect(table.getByRole("columnheader")).toHaveCount(10);
  const bondRow = page
    .getByTestId("performance-row")
    .filter({ hasText: BOND_ISIN });
  await expect(bondRow).toContainText("USD");
  await expect(bondRow).toContainText("1.000");
  await expect(bondRow).toContainText("1,000.00");
  await expect(bondRow).toContainText("1,059.81");
  await expect(bondRow).toContainText("4.473%");
  const totalRow = page
    .getByTestId("performance-row")
    .filter({ hasText: "TOTAL" });
  await expect(totalRow).toContainText("1,059.81");
  await expect(totalRow).toContainText("4.473%");

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
