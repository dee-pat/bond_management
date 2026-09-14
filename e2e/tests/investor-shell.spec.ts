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
  await expect(
    homeBreadcrumbs.getByRole("link", { name: "Home" })
  ).toBeVisible();
  await expect(homeBreadcrumbs.getByText("/", { exact: true })).toHaveCount(1);
  await expect(
    homeBreadcrumbs.getByText("Bond Investor", { exact: true })
  ).toBeVisible();
  await expect(page.getByTestId("bootstrap-status")).toHaveCount(0);
  await expect(page.locator(".investor-shell")).toBeVisible();
  await expect(page.locator(".investor-navigation")).toBeVisible();
  await expect(page.locator(".investor-page-header")).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Investor navigation" })
      .getByRole("link")
  ).toHaveCount(8);
  await expect(page.getByTestId("investor-shell")).not.toContainText("Create");
});

test("uses the Vue homepage by default and links back from Desk", async ({
  page,
}) => {
  await page.goto("/desk");

  await expect(page).toHaveURL(/\/bond-investor\/?$/);
  await expect(
    page.getByRole("heading", { name: "Bond Investor" })
  ).toBeVisible();

  await page.goto("/desk/bond-investor");
  await expect(
    page.getByRole("link", { name: "Open Investor App" })
  ).toHaveAttribute("href", "/bond-investor");
});

test("keeps a nested investor route stable across refresh", async ({
  page,
}) => {
  await page.goto("/bond-investor/transactions");

  await expect(
    page.getByRole("heading", { name: "Bond Transactions" })
  ).toBeVisible();
  const breadcrumbs = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(
    breadcrumbs.getByText("Bond Investor", { exact: true })
  ).toBeVisible();
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

test("keeps native shell chrome outside the main scroll region", async ({
  page,
}) => {
  await page.goto("/bond-investor/transactions");
  await expect(
    page.getByRole("heading", { name: "Bond Transactions" })
  ).toBeVisible();
  await expect(page.getByTestId("desk-pagination")).toBeVisible();

  const scrollLayout = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".investor-shell");
    const navigation = document.querySelector<HTMLElement>(
      ".investor-navigation"
    );
    const content = document.querySelector<HTMLElement>(
      ".investor-page-content"
    );
    const pageHeader = document.querySelector<HTMLElement>(
      ".investor-page-header"
    );

    if (!shell || !navigation || !content || !pageHeader) {
      throw new Error("Investor scroll layout is incomplete");
    }

    const rect = (element: HTMLElement) => {
      const bounds = element.getBoundingClientRect();
      return {
        top: bounds.top,
        bottom: bounds.bottom,
        height: bounds.height,
      };
    };
    const chromePositions = () => ({
      navigation: rect(navigation),
      pageHeader: rect(pageHeader),
    });

    const beforeScroll = chromePositions();
    const spacer = document.createElement("div");
    spacer.style.height = "100vh";
    spacer.style.flex = "0 0 auto";
    content.append(spacer);

    let scrollContainer = content.parentElement;
    while (scrollContainer && scrollContainer !== shell) {
      if (scrollContainer.scrollHeight > scrollContainer.clientHeight) {
        scrollContainer.scrollTop = 1;
        if (scrollContainer.scrollTop > 0) {
          break;
        }
      }
      scrollContainer = scrollContainer.parentElement;
    }
    if (!scrollContainer || scrollContainer === shell) {
      spacer.remove();
      throw new Error("Investor content scroll region is incomplete");
    }

    scrollContainer.scrollTop = Math.min(
      120,
      scrollContainer.scrollHeight - scrollContainer.clientHeight
    );
    const contentScrollTop = scrollContainer.scrollTop;
    const afterScroll = chromePositions();
    const documentScrollTop = document.scrollingElement?.scrollTop ?? 0;
    spacer.remove();
    scrollContainer.scrollTop = 0;

    return {
      viewportHeight: window.innerHeight,
      documentScrollHeight: document.documentElement.scrollHeight,
      shellHeight: shell.getBoundingClientRect().height,
      navigation: beforeScroll.navigation,
      pageHeader: beforeScroll.pageHeader,
      contentScrollTop,
      documentScrollTop,
      afterScroll,
    };
  });

  expect(scrollLayout.shellHeight).toBeGreaterThanOrEqual(
    scrollLayout.viewportHeight - 1
  );
  expect(scrollLayout.shellHeight).toBeLessThanOrEqual(
    scrollLayout.viewportHeight + 1
  );
  expect(scrollLayout.documentScrollHeight).toBeLessThanOrEqual(
    scrollLayout.viewportHeight + 1
  );
  expect(scrollLayout.contentScrollTop).toBeGreaterThan(0);
  expect(scrollLayout.documentScrollTop).toBe(0);
  expect(scrollLayout.afterScroll.navigation.top).toBe(
    scrollLayout.navigation.top
  );
  expect(scrollLayout.afterScroll.pageHeader.top).toBe(
    scrollLayout.pageHeader.top
  );
  expect(scrollLayout.navigation.top).toBe(0);
  expect(scrollLayout.pageHeader.top).toBe(0);
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
