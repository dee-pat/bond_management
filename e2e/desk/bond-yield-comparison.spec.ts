import { expect, test } from "@playwright/test";

// Seeded by `tests/investor_ui_seed.py` with stored yields in early 2095.
const seededBond = "UI-TEST-BOND-001";
const reportRoute =
  "/desk/query-report/Bond%20Yield%20Comparison?from_date=2095-01-01&to_date=2095-01-03";

test("lists stored yields and opens the investor chart", async ({ page }) => {
  await page.goto(reportRoute);

  await expect(
    page.locator(".dt-row").filter({ hasText: seededBond }).first()
  ).toBeVisible();

  await page.getByRole("button", { name: "Open chart" }).click();
  await expect(page).toHaveURL(/\/bond-investor\/yield-comparison$/);
  await expect(
    page.getByRole("heading", { name: "Bond Yield Comparison" })
  ).toBeVisible();
});
