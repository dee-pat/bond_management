import { expect, test } from "@playwright/test";

const TRANSACTION_REFERENCE = "UI-TEST-TRANSACTION-001";
const BOND_ISIN = "UI-TEST-BOND-001";

test("browses the assigned transaction list and read-only detail", async ({
  page,
}) => {
  await page.goto("/bond-investor/transactions");

  await expect(
    page.getByRole("heading", { name: "Bond Transactions" })
  ).toBeVisible();
  await expect(page.getByRole("columnheader")).toHaveCount(8);
  await expect(
    page.getByRole("columnheader", { name: "Transaction Type" })
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Quantity/ Face Value" })
  ).toBeVisible();

  await page.getByLabel("Portfolio Name").selectOption({
    label: "UI Test Portfolio",
  });
  const row = page.getByTestId("transaction-row").filter({
    hasText: TRANSACTION_REFERENCE,
  });
  await expect(row).toContainText("Purchase");
  await expect(row).toContainText(BOND_ISIN);
  await expect(row).toContainText("105.000000");
  const viewPdf = row.getByRole("link", {
    name: `View transaction ${TRANSACTION_REFERENCE} PDF`,
  });
  const downloadPdf = row.getByRole("link", {
    name: `Download transaction ${TRANSACTION_REFERENCE} PDF`,
  });
  await expect(viewPdf).toHaveAttribute("href", /\/private\/files\/.+\.pdf$/);
  await expect(viewPdf).toHaveAttribute("target", "_blank");
  const downloadPromise = page.waitForEvent("download");
  await downloadPdf.click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/\.pdf$/);

  await row
    .getByRole("link", {
      name: `View transaction ${TRANSACTION_REFERENCE}`,
      exact: true,
    })
    .click();

  await expect(page).toHaveURL(
    new RegExp(`/bond-investor/transactions/${TRANSACTION_REFERENCE}$`)
  );
  await expect(
    page.getByRole("heading", { name: TRANSACTION_REFERENCE })
  ).toBeVisible();
  const detail = page.getByTestId("transaction-detail");
  await expect(detail).toContainText("Settlement Amount");
  await expect(detail).toContainText(/USD.*1,051\.00/);
  await expect(detail).toContainText("30E/360");
  await expect(
    page.getByRole("link", {
      name: `View transaction ${TRANSACTION_REFERENCE} PDF`,
    })
  ).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: `Download transaction ${TRANSACTION_REFERENCE} PDF`,
    })
  ).toBeVisible();
  await expect(page.getByText("Read only")).toBeVisible();
  const shell = page.getByTestId("investor-shell");
  await expect(shell).not.toContainText("Create");
  await expect(shell).not.toContainText("Edit");
  await expect(shell).not.toContainText("Delete");

  await page.reload();
  await expect(page).toHaveURL(
    new RegExp(`/bond-investor/transactions/${TRANSACTION_REFERENCE}$`)
  );
  await expect(
    page.getByRole("heading", { name: TRANSACTION_REFERENCE })
  ).toBeVisible();
});
