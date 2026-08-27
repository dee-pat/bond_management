import { expect, test } from "@playwright/test";

const TRANSACTION_REFERENCE = "UI-TEST-TRANSACTION-001";

test("browses an assigned transaction without mobile overflow", async ({
  page,
}) => {
  await page.goto("/bond-investor/transactions");

  const row = page.getByTestId("transaction-row").filter({
    hasText: TRANSACTION_REFERENCE,
  });
  await expect(row).toBeVisible();
  await row
    .getByRole("link", {
      name: `View transaction ${TRANSACTION_REFERENCE}`,
      exact: true,
    })
    .click();

  await expect(
    page.getByRole("heading", { name: TRANSACTION_REFERENCE })
  ).toBeVisible();
  await expect(page.getByTestId("transaction-detail")).toContainText(
    "Settlement Amount"
  );
  await expect(
    page.getByRole("link", {
      name: `Download transaction ${TRANSACTION_REFERENCE} PDF`,
    })
  ).toBeVisible();

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
