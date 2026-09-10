import { expect, test } from "@playwright/test";

test("renders the investor shell within the Pixel 7 viewport", async ({
  page,
}) => {
  await page.goto("/bond-investor");

  await expect(
    page.getByRole("heading", { name: "Bond Investor" })
  ).toBeVisible();
  await expect(page.getByTestId("bootstrap-status")).toHaveCount(0);

  const navigation = page.getByRole("navigation", {
    name: "Investor navigation",
  });
  await expect(page.locator('[data-slot="mobile-shell"]')).toBeVisible();
  await expect(page.locator('[data-slot="mobile-nav"]')).toBeVisible();
  await expect(
    navigation.locator('[data-slot="mobile-nav-item"]')
  ).toHaveCount(8);
  await expect(navigation.getByRole("button", { name: "Home" })).toHaveCount(
    1
  );
  await navigation.getByRole("link", { name: "Bond Statements" }).click();
  await expect(
    page.getByRole("heading", { name: "Bond Statements" })
  ).toBeVisible();

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
