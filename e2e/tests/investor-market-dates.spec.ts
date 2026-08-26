import { expect, test } from "@playwright/test";

const BOND_ISIN = "UI-TEST-BOND-001";
const MARKET_DATE = "02 Jan 2025";

test("browses market history, persisted prices, and yield curve", async ({
  page,
}) => {
  await page.goto("/bond-investor/market-dates");

  await expect(
    page.getByRole("heading", { name: "Bond Market Dates" })
  ).toBeVisible();
  await expect(page.getByRole("columnheader")).toHaveCount(1);
  await expect(page.getByRole("columnheader", { name: "Date" })).toBeVisible();

  const row = page.getByTestId("market-date-row").filter({
    hasText: MARKET_DATE,
  });
  await expect(row).toBeVisible();
  await row.getByRole("link", { name: /^View market date BMD-/ }).click();

  await expect(page).toHaveURL(/\/bond-investor\/market-dates\/BMD-\d+$/);
  await expect(page.getByRole("heading", { name: MARKET_DATE })).toBeVisible();
  const prices = page.getByTestId("market-prices");
  await expect(prices.getByRole("columnheader")).toHaveCount(7);
  await expect(
    prices.getByRole("columnheader", { name: "Principal Factor" })
  ).toBeVisible();
  await expect(
    prices.getByRole("columnheader", {
      name: "Weighted Average Principal Repayment Date",
    })
  ).toBeVisible();
  await expect(prices).toContainText(BOND_ISIN);
  await expect(prices).toContainText("1.000000");
  await expect(prices).toContainText("102.500000");
  await expect(prices).toContainText("USD");
  await expect(prices).toContainText("01 Jan 2027");

  const curve = page.getByTestId("yield-curve");
  await expect(
    curve.getByRole("img", {
      name: "Yield curve by currency and weighted average principal repayment",
    })
  ).toBeVisible();
  await expect(curve.getByRole("listitem").filter({ hasText: "USD" })).toBeVisible();
  await expect(
    curve.locator(`[aria-label^="${BOND_ISIN}, USD,"]`)
  ).toBeVisible();
  await expect(page.getByText("Read only")).toBeVisible();
  await expect(page.getByTestId("investor-shell")).not.toContainText(
    "Copy cash flows"
  );

  await page.reload();
  await expect(page).toHaveURL(/\/bond-investor\/market-dates\/BMD-\d+$/);
  await expect(page.getByRole("heading", { name: MARKET_DATE })).toBeVisible();
});
