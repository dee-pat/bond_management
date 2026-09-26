import { expect, test } from "@playwright/test";

const PORTFOLIO_NAME = "UI Test Portfolio";

test("browses an assigned statement without mobile overflow", async ({
  page,
}) => {
  await page.goto("/bond-investor/statements");

  const row = page.getByTestId("statement-row").filter({
    hasText: PORTFOLIO_NAME,
  });
  await expect(row).toBeVisible();
  await row.getByRole("link", { name: /^View statement BS-[^ ]+$/ }).click();

  await expect(
    page.getByRole("heading", { name: "31 Dec 2025" })
  ).toBeVisible();
  await expect(page.getByTestId("statement-holdings")).toContainText(
    "UI-TEST-BOND-001"
  );
  await expect(
    page.getByRole("link", { name: "View statement dated 31 Dec 2025 PDF" })
  ).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: "Download statement dated 31 Dec 2025 reconciliation report",
    })
  ).toBeVisible();

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
