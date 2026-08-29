import { expect, test } from "@playwright/test";

const PORTFOLIO_NAME = "UI Test Portfolio";
const BOND_ISIN = "UI-TEST-BOND-001";

test("browses the assigned statement list and read-only detail", async ({
  page,
}) => {
  await page.goto("/bond-investor/statements");

  await expect(
    page.getByRole("heading", { name: "Bond Statements" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Statement history" }),
  ).toHaveCount(0);
  await expect(page.getByRole("columnheader")).toHaveCount(3);
  const statementDateHeader = page.getByRole("columnheader", {
    name: "Statement Date",
  });
  await expect(statementDateHeader).toBeVisible();
  await expect(statementDateHeader).toHaveAttribute("aria-sort", "descending");
  await expect(
    page.getByRole("columnheader", { name: "Reconciliation Status" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Filter .*Date/ })).toHaveCount(
    0,
  );

  await page
    .getByRole("combobox", { name: "Portfolio Name", exact: true })
    .selectOption({
      label: PORTFOLIO_NAME,
    });
  await page
    .getByRole("combobox", { name: "Reconciliation Status", exact: true })
    .selectOption("Matched");
  const row = page.getByTestId("statement-row").filter({
    hasText: PORTFOLIO_NAME,
  });
  await expect(row).toContainText("Matched");
  await expect(row).toContainText("31 Dec 2025");
  const statementLink = row.getByRole("link", {
    name: /^View statement BS-[^ ]+$/,
  });
  const statementName = (
    await statementLink.getAttribute("aria-label")
  )?.replace("View statement ", "");
  expect(statementName).toBeTruthy();
  await expect(row).not.toContainText(statementName!);
  await expect(row.getByText("Download PDF")).toHaveCount(0);
  await expect(row.getByText("Download reconciliation report")).toHaveCount(0);

  await statementLink.click();

  await expect(page).toHaveURL(/\/bond-investor\/statements\/BS-\d+$/);
  await expect(
    page.getByRole("heading", { name: "31 Dec 2025" }),
  ).toBeVisible();
  const detail = page.getByTestId("statement-detail");
  await expect(detail).toContainText("Market Price Posting");
  await expect(detail).toContainText("Matched");
  const holdings = page.getByTestId("statement-holdings");
  await expect(holdings).toContainText(BOND_ISIN);
  await expect(holdings).toContainText("1.000000");
  await expect(holdings).toContainText("USD");
  await expect(page.getByText("Read only")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "PDF Attachment" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "View statement dated 31 Dec 2025 PDF" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Quantity Reconciliation Report" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: "Download statement dated 31 Dec 2025 reconciliation report",
    }),
  ).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/bond-investor\/statements\/BS-\d+$/);
  await expect(
    page.getByRole("heading", { name: "31 Dec 2025" }),
  ).toBeVisible();
});
