import { expect, test } from "@playwright/test";

test("links from Desk to the Vue investor app", async ({ page }) => {
  await page.goto("/desk/bond-investor");
  await expect(page.locator("body")).toHaveAttribute(
    "data-ajax-state",
    "complete"
  );
  await expect(page.locator(".page-head")).toBeVisible();

  const investorLink = page.locator(".page-head .bond-investor-app-link");
  await expect(investorLink).toBeVisible();
  await expect(investorLink).toHaveAttribute("href", "/bond-investor");
  await expect(investorLink).toContainText("Open Investor App");
});
