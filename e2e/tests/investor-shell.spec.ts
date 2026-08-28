import { expect, test } from "@playwright/test";

import { authenticateInvestor } from "../support/auth";

test("renders the authenticated investor compatibility shell", async ({
  page,
}) => {
  await page.goto("/bond-investor");

  await expect(page).toHaveURL(/\/bond-investor\/?$/);
  await expect(
    page.getByRole("heading", { name: "Bond Investor" })
  ).toBeVisible();
  const homeBreadcrumbs = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(homeBreadcrumbs.getByRole("link", { name: "Home" })).toBeVisible();
  await expect(homeBreadcrumbs.getByText("/", { exact: true })).toHaveCount(1);
  await expect(
    homeBreadcrumbs.getByText("Bond Investor", { exact: true })
  ).toBeVisible();
  await expect(page.getByTestId("bootstrap-status")).toHaveCount(0);
  await expect(
    page
      .getByRole("navigation", { name: "Investor navigation" })
      .getByRole("link")
  ).toHaveCount(8);
  await expect(page.getByTestId("investor-shell")).not.toContainText("Create");
});

test("keeps a nested investor route stable across refresh", async ({
  page,
}) => {
  await page.goto("/bond-investor/transactions");

  await expect(
    page.getByRole("heading", { name: "Bond Transactions" })
  ).toBeVisible();
  const breadcrumbs = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(breadcrumbs.getByText("Bond Investor", { exact: true })).toBeVisible();
  await expect(
    breadcrumbs.getByText("Bond Transactions", { exact: true })
  ).toBeVisible();
  await expect(breadcrumbs.getByText("/", { exact: true })).toHaveCount(2);
  await expect(
    page.getByRole("heading", { name: "Transaction history" })
  ).toHaveCount(0);

  await page.reload();
  await expect(page).toHaveURL(/\/bond-investor\/transactions$/);
  await expect(
    page.getByRole("heading", { name: "Bond Transactions" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Transaction history" })
  ).toHaveCount(0);
});

test.describe("expired investor session", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("preserves the intended nested route", async ({ page }) => {
    await authenticateInvestor(page.request);
    await page.goto("/bond-investor");
    await expect(
      page.getByRole("heading", { name: "Bond Investor" })
    ).toBeVisible();

    const csrfToken = await page.evaluate(
      () => (window as typeof window & { csrf_token?: string }).csrf_token
    );
    const logout = await page.request.post(
      "/api/method/frappe.handler.logout",
      {
        headers: { "X-Frappe-CSRF-Token": csrfToken ?? "" },
      }
    );
    expect(logout.ok()).toBeTruthy();

    await page.goto("/bond-investor/transactions");
    await expect(page).toHaveURL(
      /\/login\?redirect-to=%2Fbond-investor%2Ftransactions$/
    );
  });
});
