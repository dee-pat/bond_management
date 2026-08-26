import { expect, test } from "@playwright/test";

const BOND_ISIN = "UI-TEST-BOND-001";

test("browses a shared bond without mobile overflow", async ({ page }) => {
  await page.goto("/bond-investor/bonds");

  const row = page.getByTestId("bond-row").filter({ hasText: BOND_ISIN });
  await expect(row).toBeVisible();
  await row.getByRole("link", { name: `View bond ${BOND_ISIN}` }).click();

  await expect(page.getByRole("heading", { name: BOND_ISIN })).toBeVisible();
  await expect(page.getByTestId("principal-schedule")).toContainText(
    "01 Jan 2027"
  );
  await expect(page.getByTestId("coupon-schedule")).toContainText(
    "01 Jul 2025"
  );

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
