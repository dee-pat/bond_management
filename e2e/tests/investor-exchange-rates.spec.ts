import { expect, test } from "@playwright/test";

const EXCHANGE_RATE_DATE = "03 Jan 2025";
const FROM_CURRENCY = "GBP";

test("browses shared exchange rates and persisted reciprocal values", async ({
  page,
}) => {
  await page.goto("/bond-investor/exchange-rates");

  await expect(
    page.getByRole("heading", { name: "Bond Exchange Rates" })
  ).toBeVisible();
  await expect(page.getByRole("columnheader")).toHaveCount(5);
  for (const header of [
    "Rate Date",
    "From Currency",
    "To Currency",
    "Rate",
    "Reverse Rate",
  ]) {
    await expect(
      page.getByRole("columnheader", { name: header, exact: true })
    ).toBeVisible();
  }

  const row = page
    .getByTestId("exchange-rate-row")
    .filter({ hasText: FROM_CURRENCY })
    .filter({ hasText: EXCHANGE_RATE_DATE });
  await expect(row).toContainText(EXCHANGE_RATE_DATE);
  await expect(row).toContainText("USD");
  await expect(row).toContainText("1.250000000000");
  await expect(row).toContainText("0.800000000000");
  await row.getByRole("link", { name: /^View exchange rate EXR-/ }).click();

  await expect(page).toHaveURL(/\/bond-investor\/exchange-rates\/EXR-/);
  await expect(
    page.getByRole("heading", { name: FROM_CURRENCY })
  ).toBeVisible();
  const detail = page.getByTestId("exchange-rate-detail");
  await expect(detail).toContainText(EXCHANGE_RATE_DATE);
  await expect(detail).toContainText("USD");
  await expect(detail).toContainText("Manual");
  await expect(detail).toContainText("1.250000000000");
  await expect(detail).toContainText("0.800000000000");
  await expect(detail).toContainText("Statement");
  await expect(detail).toContainText("—");
  await expect(page.getByText("Read only")).toBeVisible();
  await expect(page.getByTestId("investor-shell")).not.toContainText("Edit");

  await page.reload();
  await expect(page).toHaveURL(/\/bond-investor\/exchange-rates\/EXR-/);
  await expect(
    page.getByRole("heading", { name: FROM_CURRENCY })
  ).toBeVisible();
});
