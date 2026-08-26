import { expect, test } from "@playwright/test";

const EXCHANGE_RATE_DATE = "03 Jan 2025";
const FROM_CURRENCY = "GBP";

test("browses an exchange rate without mobile overflow", async ({ page }) => {
  await page.goto("/bond-investor/exchange-rates");

  const row = page
    .getByTestId("exchange-rate-row")
    .filter({ hasText: FROM_CURRENCY })
    .filter({ hasText: EXCHANGE_RATE_DATE });
  await expect(row).toContainText("1.250000000000");
  await expect(row).toContainText("0.800000000000");
  await row.getByRole("link", { name: /^View exchange rate EXR-/ }).click();

  await expect(
    page.getByRole("heading", { name: FROM_CURRENCY })
  ).toBeVisible();
  const detail = page.getByTestId("exchange-rate-detail");
  await expect(detail).toContainText("Manual");
  await expect(detail).toContainText("1.250000000000");
  await expect(detail).toContainText("0.800000000000");

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
