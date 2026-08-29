import { expect, test } from "@playwright/test";

const TRANSACTION_REFERENCE = "UI-TEST-TRANSACTION-001";
const BOND_ISIN = "UI-TEST-BOND-001";

test("browses the assigned transaction list and read-only detail", async ({
  page,
}) => {
  await page.goto("/bond-investor/transactions");

  await expect(
    page.getByRole("heading", { name: "Bond Transactions" }),
  ).toBeVisible();
  await expect(page.getByRole("columnheader")).toHaveCount(7);
  await expect(
    page.getByRole("columnheader", { name: "Transaction Type" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Quantity/ Face Value" }),
  ).toBeVisible();
  const settlementHeader = page.getByRole("columnheader", {
    name: "Settlement Date",
  });
  await expect(settlementHeader).toHaveAttribute("aria-sort", "descending");
  await expect(page.getByRole("button", { name: /Filter .*Date/ })).toHaveCount(
    0,
  );

  await page
    .getByRole("combobox", { name: "Portfolio Name", exact: true })
    .selectOption({
      label: "UI Test Portfolio",
    });
  const row = page.getByTestId("transaction-row").filter({
    hasText: BOND_ISIN,
  });
  await expect(row).toContainText("Purchase");
  await expect(row).toContainText(BOND_ISIN);
  await expect(row).toContainText("105.000000");
  await expect(row).not.toContainText(TRANSACTION_REFERENCE);
  const sortResponse = page.waitForResponse(
    (response) =>
      response.url().includes("investor.get_transactions") &&
      response.url().includes("sort_by=settlement_date"),
  );
  await settlementHeader.getByRole("button").click();
  await sortResponse;
  await expect(settlementHeader).toHaveAttribute("aria-sort", "ascending");

  const filterResponse = page.waitForResponse(
    (response) =>
      response.url().includes("investor.get_transactions") &&
      response.url().includes("filter_field=isin"),
  );
  await row
    .getByRole("button", { name: `Filter ISIN by ${BOND_ISIN}` })
    .click();
  await filterResponse;
  await expect(page.getByTestId("active-filters")).toContainText(BOND_ISIN);

  const pageLengthResponse = page.waitForResponse(
    (response) =>
      response.url().includes("investor.get_transactions") &&
      response.url().includes("page_length=50"),
  );
  await page.getByRole("button", { name: "50 rows per page" }).click();
  await pageLengthResponse;
  await expect(
    page.getByRole("button", { name: "50 rows per page" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("columnheader", { name: "PDF Attachment" }),
  ).toHaveCount(0);
  await expect(
    row.getByRole("link", {
      name: `View transaction ${TRANSACTION_REFERENCE} PDF`,
    }),
  ).toHaveCount(0);
  await expect(
    row.getByRole("link", {
      name: `Download transaction ${TRANSACTION_REFERENCE} PDF`,
    }),
  ).toHaveCount(0);

  await row
    .getByRole("link", {
      name: `View transaction ${TRANSACTION_REFERENCE}`,
      exact: true,
    })
    .click();

  await expect(page).toHaveURL(
    new RegExp(`/bond-investor/transactions/${TRANSACTION_REFERENCE}$`),
  );
  const detailBreadcrumbs = page.getByRole("navigation", {
    name: "Breadcrumb",
  });
  await expect(
    detailBreadcrumbs.getByText("Bond Transactions", { exact: true }),
  ).toBeVisible();
  await expect(
    detailBreadcrumbs.getByText("Bond Transaction", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: TRANSACTION_REFERENCE }),
  ).toBeVisible();
  const detail = page.getByTestId("transaction-detail");
  await expect(detail).toContainText("Settlement Amount");
  await expect(detail).toContainText(/USD.*1,051\.00/);
  await expect(detail).toContainText("30E/360");
  await expect(
    page.getByRole("link", {
      name: `View transaction ${TRANSACTION_REFERENCE} PDF`,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: `Download transaction ${TRANSACTION_REFERENCE} PDF`,
    }),
  ).toBeVisible();
  await expect(page.getByText("Read only")).toBeVisible();
  const shell = page.getByTestId("investor-shell");
  await expect(shell).not.toContainText("Create");
  await expect(shell).not.toContainText("Edit");
  await expect(shell).not.toContainText("Delete");

  await page.reload();
  await expect(page).toHaveURL(
    new RegExp(`/bond-investor/transactions/${TRANSACTION_REFERENCE}$`),
  );
  await expect(
    page.getByRole("heading", { name: TRANSACTION_REFERENCE }),
  ).toBeVisible();
});
