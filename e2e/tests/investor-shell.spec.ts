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
  await expect(page.locator('[data-slot="desktop-shell"]')).toBeVisible();
  await expect(page.locator('[data-slot="sidebar"]')).toBeVisible();
  await expect(
    page.locator('[data-slot="desktop-shell-content"]')
  ).toBeVisible();
  await expect(
    page.locator('[data-slot="desktop-shell-content"] [data-slot="scroll-area"]')
  ).toBeVisible();
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
    const shellContent = document.querySelector<HTMLElement>(
      '[data-slot="desktop-shell-content"]'
    );
    const navigation = document.querySelector<HTMLElement>(
      '[data-slot="sidebar"]'
    );
    const scrollArea = shellContent?.querySelector<HTMLElement>(
      '[data-slot="scroll-area"]'
    );
    const viewport = shellContent?.querySelector<HTMLElement>(
      '[data-slot="scroll-area-viewport"]'
    );
    const content = viewport?.querySelector<HTMLElement>("main");
    const pageHeader = document.querySelector<HTMLElement>(
      ".investor-page-header"
    );
    const pagination = document.querySelector<HTMLElement>(
      '[data-testid="desk-pagination"]'
    );

    if (
      !shell ||
      !shellContent ||
      !navigation ||
      !scrollArea ||
      !viewport ||
      !content ||
      !pageHeader ||
      !pagination
    ) {
      throw new Error("Investor scroll layout is incomplete");
    }

    const computedStyle = (element: HTMLElement) => getComputedStyle(element);
    const rect = (element: HTMLElement) => {
      const bounds = element.getBoundingClientRect();
      return {
        top: bounds.top,
        bottom: bounds.bottom,
        height: bounds.height,
      };
    };
    const chromePositions = () => ({
      shellContent: rect(shellContent),
      navigation: rect(navigation),
      pageHeader: rect(pageHeader),
      viewport: rect(viewport),
    });

    const beforeScroll = chromePositions();
    const spacer = document.createElement("div");
    spacer.style.height = "100vh";
    spacer.style.flex = "0 0 auto";
    content.append(spacer);
    viewport.scrollTop = Math.min(
      120,
      viewport.scrollHeight - viewport.clientHeight
    );
    const contentScrollTop = viewport.scrollTop;
    const afterScroll = chromePositions();
    const documentScrollTop = document.scrollingElement?.scrollTop ?? 0;
    spacer.remove();
    viewport.scrollTop = 0;

    return {
      viewportHeight: window.innerHeight,
      documentScrollHeight: document.documentElement.scrollHeight,
      shellHeight: shell.getBoundingClientRect().height,
      shellContent: beforeScroll.shellContent,
      navigation: beforeScroll.navigation,
      pageHeader: beforeScroll.pageHeader,
      viewport: beforeScroll.viewport,
      viewportOverflowY: computedStyle(viewport).overflowY,
      scrollAreaOverflow: computedStyle(scrollArea).overflow,
      navigationOverflow: computedStyle(navigation).overflow,
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
  expect(scrollLayout.viewportOverflowY).toBe("scroll");
  expect(scrollLayout.scrollAreaOverflow).toBe("hidden");
  expect(scrollLayout.navigationOverflow).toBe("hidden");
  expect(scrollLayout.paginationPosition).toBe("sticky");
  expect(scrollLayout.contentScrollTop).toBeGreaterThan(0);
  expect(scrollLayout.documentScrollTop).toBe(0);
  expect(scrollLayout.afterScroll.shellContent.top).toBe(
    scrollLayout.shellContent.top
  );
  expect(scrollLayout.afterScroll.navigation.top).toBe(
    scrollLayout.navigation.top
  );
  expect(scrollLayout.afterScroll.pageHeader.top).toBe(
    scrollLayout.pageHeader.top
  );
  expect(scrollLayout.afterScroll.viewport.top).toBe(
    scrollLayout.viewport.top
  );
  expect(scrollLayout.shellContent.top).toBe(0);
  expect(scrollLayout.navigation.top).toBe(0);
  expect(scrollLayout.pageHeader.top).toBe(scrollLayout.shellContent.top);
  expect(scrollLayout.viewport.top).toBe(scrollLayout.pageHeader.bottom);
  expect(scrollLayout.navigation.bottom).toBe(
    scrollLayout.shellContent.bottom
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
