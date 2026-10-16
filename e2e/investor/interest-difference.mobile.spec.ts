import { expect, test } from "@playwright/test";

import { selectFrappeOption } from "./helpers/controls";

test("keeps the interest difference table inside the mobile page", async ({
  page,
}) => {
  await page.goto("/bond-investor/interest-difference");
  await selectFrappeOption(page, "Portfolio (required)", "UI Test Portfolio");
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const table = page.getByTestId("interest-difference-table");
  await expect(table.getByRole("table")).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Currency" })).toBeVisible();
  await expect(page.getByTestId("interest-difference-total-row")).toBeVisible();

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
