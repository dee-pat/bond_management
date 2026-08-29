import { expect, test } from "@playwright/test";

const BOND_ISIN = "UI-TEST-BOND-001";
const MARKET_DATE = "02 Jan 2025";

test("browses a market date and yield curve without mobile overflow", async ({
  page,
}) => {
  await page.goto("/bond-investor/market-dates");

  const row = page.getByTestId("market-date-row").filter({
    hasText: MARKET_DATE,
  });
  await expect(row).toBeVisible();
  await row.getByRole("link", { name: /^View market date BMD-/ }).click();

  await expect(page.getByRole("heading", { name: MARKET_DATE })).toBeVisible();
  await expect(page.getByTestId("market-prices")).toContainText(BOND_ISIN);
  await expect(
    page.getByRole("img", {
      name: "Yield curve by currency and weighted average principal repayment",
    })
  ).toBeVisible();

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
