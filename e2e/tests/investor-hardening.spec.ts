import { expect, test, type Route } from "@playwright/test";

import { authenticateInvestor } from "../support/auth";
import { selectFrappeOption } from "../support/controls";

const INVESTOR_API =
  "**/api/method/bond_management.bond_management.api.investor";

test("announces client navigation with route titles and heading focus", async ({
  page,
}) => {
  await page.goto("/bond-investor");

  const homeHeading = page.getByRole("heading", { name: "Bond Investor" });
  await expect(page).toHaveTitle("Bond Investor");
  await expect(homeHeading).toBeFocused();
  await expect(page.getByTestId("investor-shell")).not.toContainText(
    "subsequent migration slices"
  );

  await page
    .getByRole("navigation", { name: "Investor navigation" })
    .getByRole("link", { name: "Bond Transactions" })
    .click();

  const transactionHeading = page.getByRole("heading", {
    name: "Bond Transactions",
  });
  await expect(page).toHaveTitle("Bond Transactions · Bond Investor");
  await expect(transactionHeading).toBeFocused();
  await expect(
    page
      .getByRole("navigation", { name: "Investor navigation" })
      .getByRole("link", { name: "Bond Transactions" })
  ).toHaveAttribute("aria-current", "page");
});

test("shows loading, failure, retry, and empty transaction states", async ({
  page,
}) => {
  const firstRequestStarted = deferred();
  const releaseFirstRequest = deferred();
  let attempts = 0;

  await page.route(`${INVESTOR_API}.get_transactions*`, async (route) => {
    attempts += 1;
    if (attempts === 1) {
      firstRequestStarted.resolve();
      await releaseFirstRequest.promise;
      await route.fulfill({ status: 500, body: "{}" });
      return;
    }

    const transactionPage = {
      data: [],
      pagination: { start: 0, page_length: 20, has_more: false },
    };
    await fulfillJson(route, {
      message: transactionPage,
      data: transactionPage,
    });
  });

  await page.goto("/bond-investor/transactions");
  await firstRequestStarted.promise;
  await expect(page.getByText("Loading transactions…")).toBeVisible();

  releaseFirstRequest.resolve();
  await expect(page.getByRole("alert")).toContainText(
    "Transactions could not be loaded"
  );
  await page.getByRole("button", { name: "Retry" }).click();

  await expect(page.getByTestId("transactions-empty")).toContainText(
    "No transactions match"
  );
  expect(attempts).toBe(2);
});

test("keeps a newer yield result when an older request finishes last", async ({
  page,
}) => {
  const firstRequestStarted = deferred();
  const releaseFirstRequest = deferred();
  let attempts = 0;

  await page.route(
    `${INVESTOR_API}.get_bond_yield_comparison*`,
    async (route) => {
      attempts += 1;
      if (attempts === 1) {
        firstRequestStarted.resolve();
        await releaseFirstRequest.promise;
        await fulfillJson(route, yieldResponse("STALE-BOND"));
        return;
      }

      await fulfillJson(route, yieldResponse("LATEST-BOND"));
    }
  );

  await page.goto("/bond-investor/yield-comparison");
  await expect(page.getByTestId("yield-comparison-initial")).toBeVisible();
  await page.getByLabel("From Date").fill("2095-01-01");
  await page.getByLabel("To Date").fill("2095-01-03");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await firstRequestStarted.promise;
  await expect(page.getByText("Loading bond yield comparison…")).toBeVisible();

  await page.getByLabel("From Date").fill("2095-01-02");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(
    page.getByTestId("yield-comparison-chart-description")
  ).toContainText("LATEST-BOND");

  releaseFirstRequest.resolve();
  await expect(
    page.getByTestId("yield-comparison-chart-description")
  ).toContainText("LATEST-BOND");
  await expect(
    page.getByTestId("yield-comparison-chart-description")
  ).not.toContainText("STALE-BOND");
});

test("preserves a pending yield report across responsive shell changes", async ({
  page,
}) => {
  const requestStarted = deferred();
  const releaseRequest = deferred();

  await page.setViewportSize({ width: 412, height: 915 });
  await page.route(
    `${INVESTOR_API}.get_bond_yield_comparison*`,
    async (route) => {
      requestStarted.resolve();
      await releaseRequest.promise;
      await fulfillJson(route, yieldResponse("RESPONSIVE-BOND"));
    }
  );

  await page.goto("/bond-investor/yield-comparison");
  await expect(page.getByTestId("yield-comparison-initial")).toBeVisible();
  await page.getByLabel("From Date").fill("2095-01-01");
  await page.getByLabel("To Date").fill("2095-01-03");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await requestStarted.promise;
  await expect(page.getByText("Loading bond yield comparison…")).toBeVisible();

  await page.setViewportSize({ width: 915, height: 915 });
  await expect(page.locator('[data-slot="desktop-shell"]')).toBeVisible();
  await expect(page.getByLabel("From Date")).toHaveValue("2095-01-01");
  await expect(page.getByLabel("To Date")).toHaveValue("2095-01-03");
  await expect(page.getByText("Loading bond yield comparison…")).toBeVisible();

  releaseRequest.resolve();
  await expect(
    page.getByTestId("yield-comparison-chart-description")
  ).toContainText("RESPONSIVE-BOND");
  await expect(page.getByTestId("yield-comparison-initial")).toHaveCount(0);
});

test("preserves filtered paginated transactions across responsive shell changes", async ({
  page,
}) => {
  const loadMoreStarted = deferred();
  const releaseLoadMore = deferred();
  const filteredIsin = "RESPONSIVE-FILTERED-BOND";

  await page.setViewportSize({ width: 412, height: 915 });
  await page.route(`${INVESTOR_API}.get_transactions*`, async (route) => {
    const start = Number(
      new URL(route.request().url()).searchParams.get("start") ?? 0
    );
    if (start === 20) {
      loadMoreStarted.resolve();
      await releaseLoadMore.promise;
    }
    await fulfillJson(route, transactionPage(start, filteredIsin));
  });

  await page.goto("/bond-investor/transactions");
  const rows = page.getByTestId("transaction-row");
  await expect(rows).toHaveCount(20);
  await rows
    .first()
    .getByRole("button", { name: `Filter ISIN by ${filteredIsin}` })
    .click();
  await expect(page.getByTestId("active-filters")).toContainText(filteredIsin);

  await page.getByRole("button", { name: "Load More", exact: true }).click();
  await loadMoreStarted.promise;
  await page.setViewportSize({ width: 915, height: 915 });
  await expect(page.locator('[data-slot="desktop-shell"]')).toBeVisible();
  await expect(rows).toHaveCount(20);
  await expect(page.getByTestId("active-filters")).toContainText(filteredIsin);

  releaseLoadMore.resolve();
  await expect(rows).toHaveCount(21);
  await expect(page.getByTestId("active-filters")).toContainText(filteredIsin);
});

test.describe("mid-session expiry", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("redirects with the nested route preserved", async ({ page }) => {
    await authenticateInvestor(page.request);
    await page.goto("/bond-investor/transactions");
    await expect(page.getByTestId("transaction-row").first()).toBeVisible();

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

    const expiredResponse = page.waitForResponse((response) =>
      response.url().includes("investor.get_transactions")
    );
    await selectFrappeOption(page, "Portfolio Name", "UI Test Portfolio");
    expect((await expiredResponse).status()).toBe(403);

    await expect(page).toHaveURL(
      /\/login\?redirect-to=%2Fbond-investor%2Ftransactions$/
    );
  });
});

test("keeps an authenticated record denial on its detail route", async ({
  page,
}) => {
  const path = "/bond-investor/transactions/UNKNOWN-INVESTOR-TRANSACTION";

  await page.goto(path);

  await expect(page).toHaveURL(new RegExp(`${path}$`));
  await expect(page.getByRole("alert")).toContainText(
    "unavailable or you do not have permission"
  );
});

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve = () => undefined;
  const promise = new Promise<void>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

async function fulfillJson(route: Route, payload: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

function yieldResponse(isin: string): object {
  const report = {
    filters: { from_date: "2095-01-02", to_date: "2095-01-03" },
    columns: [
      column("date", "Date", "Date"),
      column("isin", "ISIN", "Link"),
      column("currency", "CCY", "Data"),
      column("market_price", "Market Price", "Float", 3),
      column("future_xirr", "Future XIRR", "Percent", 3),
    ],
    rows: [
      {
        date: "2095-01-02",
        isin,
        currency: "USD",
        market_price: 102.5,
        future_xirr: 7.25,
      },
    ],
    chart: {
      x_field: "date",
      value_field: "future_xirr",
      series_field: "isin",
      gap_policy: "preserve",
    },
  };
  return {
    message: { report },
    data: { report },
  };
}

function transactionPage(start: number, isin: string): object {
  const data = Array.from({ length: start === 20 ? 1 : 20 }, (_, index) => ({
    name: `RESPONSIVE-TRANSACTION-${start + index}`,
    settlement_date: "2095-01-02",
    transaction_type: "Purchase",
    portfolio_name: "UI Test Portfolio",
    isin,
    trade_date: "2095-01-01",
    quantity_face_value: 10,
    price: 100,
  }));
  const pageData = {
    data,
    pagination: { start, page_length: 20, has_more: start === 0 },
  };
  return { message: pageData, data: pageData };
}

function column(
  fieldname: string,
  label: string,
  fieldtype: string,
  precision: number | null = null
): object {
  return {
    fieldname,
    label,
    fieldtype,
    options: null,
    description: null,
    precision,
  };
}
