import { expect, test } from "@playwright/test";

const BOND_ISIN = "UI-TEST-BOND-001";

test("browses the shared bond catalog and read-only schedules", async ({
  page,
}) => {
  await page.goto("/bond-investor/bonds");

  await expect(
    page.getByRole("heading", { name: "Bond Master" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bond catalog" })).toHaveCount(0);
  await expect(page.getByRole("columnheader")).toHaveCount(4);
  await expect(
    page.getByRole("columnheader", { name: "Bond Name" }),
  ).toBeVisible();
  const issueDateHeader = page.getByRole("columnheader", { name: "Issue Date" });
  await expect(issueDateHeader).toBeVisible();
  await expect(issueDateHeader).toHaveAttribute("aria-sort", "descending");
  await expect(
    page.getByRole("button", { name: /Filter .*Date/ }),
  ).toHaveCount(0);
  const currencyHeader = page.getByRole("columnheader", { name: "Currency" });
  const sortResponse = page.waitForResponse(
    (response) =>
      response.url().includes("investor.get_bonds") &&
      response.url().includes("sort_by=currency"),
  );
  await currencyHeader.getByRole("button").click();
  await sortResponse;
  await expect(currencyHeader).toHaveAttribute("aria-sort", "ascending");

  const row = page.getByTestId("bond-row").filter({ hasText: BOND_ISIN });
  await expect(row).toContainText("Investor UI Test Bond");
  await expect(row).toContainText("USD");
  await expect(row).toContainText("01 Jan 2025");
  const filterResponse = page.waitForResponse(
    (response) =>
      response.url().includes("investor.get_bonds") &&
      response.url().includes("filter_field=currency"),
  );
  await row.getByRole("button", { name: "Filter Currency by USD" }).click();
  await filterResponse;
  await expect(page.getByTestId("active-filters")).toContainText("USD");
  await row.getByRole("link", { name: `View bond ${BOND_ISIN}` }).click();

  await expect(page).toHaveURL(`/bond-investor/bonds/${BOND_ISIN}`);
  await expect(page.getByRole("heading", { name: BOND_ISIN })).toBeVisible();
  const detail = page.getByTestId("bond-detail");
  await expect(detail).toContainText("Investor UI Test Bond");
  await expect(detail).toContainText("Kenya Treasury Bond");
  await expect(detail).toContainText("30E/360");
  await expect(detail).toContainText("7.00%");

  const principalSchedule = page.getByTestId("principal-schedule");
  await expect(principalSchedule).toContainText("01 Jan 2027");
  await expect(principalSchedule).toContainText("100.00%");
  const couponSchedule = page.getByTestId("coupon-schedule");
  await expect(couponSchedule).toContainText("01 Jul 2025");
  await expect(couponSchedule).toContainText("3.50%");
  await expect(page.getByText("Read only")).toBeVisible();
  await expect(page.getByTestId("investor-shell")).not.toContainText("Edit");

  await page.reload();
  await expect(page).toHaveURL(`/bond-investor/bonds/${BOND_ISIN}`);
  await expect(page.getByRole("heading", { name: BOND_ISIN })).toBeVisible();
});
