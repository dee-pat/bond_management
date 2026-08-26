import { expect, test } from "@playwright/test";

const PORTFOLIO_NAME = "UI Test Portfolio";
const BOND_ISIN = "UI-TEST-BOND-001";

test("browses the assigned statement list and read-only detail", async ({
  page,
}) => {
  await page.goto("/bond-investor/statements");

  await expect(
    page.getByRole("heading", { name: "Bond Statements" })
  ).toBeVisible();
  await expect(page.getByRole("columnheader")).toHaveCount(3);
  await expect(
    page.getByRole("columnheader", { name: "Statement Date" })
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Reconciliation Status" })
  ).toBeVisible();

  await page.getByLabel("Portfolio Name").selectOption({
    label: PORTFOLIO_NAME,
  });
  await page.getByLabel("Reconciliation Status").selectOption("Matched");
  const row = page.getByTestId("statement-row").filter({
    hasText: PORTFOLIO_NAME,
  });
  await expect(row).toContainText("Matched");
  await expect(row).toContainText("31 Dec 2025");

  await row.getByRole("link", { name: /^View statement BS-/ }).click();

  await expect(page).toHaveURL(/\/bond-investor\/statements\/BS-\d+$/);
  await expect(
    page.getByRole("heading", { name: "31 Dec 2025" })
  ).toBeVisible();
  const detail = page.getByTestId("statement-detail");
  await expect(detail).toContainText("Market Price Posting");
  await expect(detail).toContainText("Matched");
  const holdings = page.getByTestId("statement-holdings");
  await expect(holdings).toContainText(BOND_ISIN);
  await expect(holdings).toContainText("1.000000");
  await expect(holdings).toContainText("USD");
  await expect(page.getByText("Read only")).toBeVisible();
  const shell = page.getByTestId("investor-shell");
  await expect(shell).not.toContainText("Attachment");
  await expect(shell).not.toContainText("Download");

  await page.reload();
  await expect(page).toHaveURL(/\/bond-investor\/statements\/BS-\d+$/);
  await expect(
    page.getByRole("heading", { name: "31 Dec 2025" })
  ).toBeVisible();
});
