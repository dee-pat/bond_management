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

test("keeps Desk shell chrome outside the main scroll region", async ({
  page,
}) => {
  await page.goto("/bond-investor/transactions");
  await expect(
    page.getByRole("heading", { name: "Bond Transactions" })
  ).toBeVisible();
  await expect(page.getByTestId("desk-pagination")).toBeVisible();

  const scrollLayout = await page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>(".investor-shell");
    const navbar = document.querySelector<HTMLElement>(".investor-navbar");
    const navigation = document.querySelector<HTMLElement>(
      ".investor-navigation"
    );
    const navigationList = document.querySelector<HTMLElement>(
      ".investor-navigation nav"
    );
    const content = document.querySelector<HTMLElement>(".investor-card");
    const pageHeader = document.querySelector<HTMLElement>(
      ".investor-page-header"
    );
    const navigationFooter = document.querySelector<HTMLElement>(
      ".investor-navigation__footer"
    );
    const pagination = document.querySelector<HTMLElement>(
      '[data-testid="desk-pagination"]'
    );

    if (
      !shell ||
      !navbar ||
      !navigation ||
      !navigationList ||
      !content ||
      !pageHeader ||
      !navigationFooter ||
      !pagination
    ) {
      throw new Error("Investor scroll layout is incomplete");
    }

    const computedStyle = (element: HTMLElement) => getComputedStyle(element);
    const rect = (element: HTMLElement) => {
      const bounds = element.getBoundingClientRect();
      return { top: bounds.top, bottom: bounds.bottom };
    };
    const chromePositions = () => ({
      navbar: rect(navbar),
      navigation: rect(navigation),
      pageHeader: rect(pageHeader),
      navigationFooter: rect(navigationFooter),
    });

    const beforeScroll = chromePositions();
    const spacer = document.createElement("div");
    spacer.style.height = "100vh";
    spacer.style.flex = "0 0 auto";
    content.append(spacer);
    content.scrollTop = Math.min(120, content.scrollHeight - content.clientHeight);
    const contentScrollTop = content.scrollTop;
    const afterScroll = chromePositions();
    const documentScrollTop = document.scrollingElement?.scrollTop ?? 0;
    spacer.remove();
    content.scrollTop = 0;

    return {
      viewportHeight: window.innerHeight,
      documentScrollHeight: document.documentElement.scrollHeight,
      shellHeight: shell.getBoundingClientRect().height,
      navbar: beforeScroll.navbar,
      navigation: beforeScroll.navigation,
      content: rect(content),
      pageHeader: beforeScroll.pageHeader,
      navigationFooter: beforeScroll.navigationFooter,
      contentOverflowY: computedStyle(content).overflowY,
      navigationOverflow: computedStyle(navigation).overflow,
      navigationListOverflowY: computedStyle(navigationList).overflowY,
      navigationFooterPosition: computedStyle(navigationFooter).position,
      paginationPosition: computedStyle(pagination).position,
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
  expect(scrollLayout.contentOverflowY).toBe("auto");
  expect(scrollLayout.navigationOverflow).toBe("hidden");
  expect(scrollLayout.navigationListOverflowY).toBe("auto");
  expect(scrollLayout.navigationFooterPosition).toBe("sticky");
  expect(scrollLayout.paginationPosition).toBe("sticky");
  expect(scrollLayout.contentScrollTop).toBeGreaterThan(0);
  expect(scrollLayout.documentScrollTop).toBe(0);
  expect(scrollLayout.afterScroll.navbar.top).toBe(scrollLayout.navbar.top);
  expect(scrollLayout.afterScroll.navigation.top).toBe(
    scrollLayout.navigation.top
  );
  expect(scrollLayout.afterScroll.pageHeader.top).toBe(
    scrollLayout.pageHeader.top
  );
  expect(scrollLayout.afterScroll.navigationFooter.bottom).toBe(
    scrollLayout.navigationFooter.bottom
  );
  expect(scrollLayout.navbar.top).toBe(0);
  expect(scrollLayout.navigation.top).toBe(scrollLayout.navbar.bottom);
  expect(scrollLayout.content.top).toBe(scrollLayout.navigation.top);
  expect(scrollLayout.pageHeader.top).toBe(scrollLayout.content.top);
  expect(scrollLayout.navigationFooter.bottom).toBe(
    scrollLayout.navigation.bottom - 10
  );
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
