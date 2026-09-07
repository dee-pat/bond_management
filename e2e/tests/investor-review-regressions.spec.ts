import { expect, test } from "@playwright/test";

const API = "**/api/method/bond_management.bond_management.api.investor";

test("omits unavailable yields while preserving a genuine zero yield", async ({
  page,
}) => {
  await page.route(`${API}.get_market_date?*`, async (route) => {
    await route.fulfill({
      json: {
        message: {
          market_date: {
            date: "2026-01-01",
            bond_market_prices: [
              marketPrice("MISSING-YIELD", null),
              marketPrice("ZERO-YIELD", 0),
            ],
          },
        },
      },
    });
  });

  await page.goto("/bond-investor/market-dates/review-yields");
  await expect(page.getByTestId("market-prices")).toContainText(
    "MISSING-YIELD"
  );
  const curve = page.getByTestId("yield-curve");
  await expect(curve.getByLabel(/^ZERO-YIELD, USD, 0\.00%/)).toBeVisible();
  await expect(curve.getByLabel(/^MISSING-YIELD,/)).toHaveCount(0);
});

test("restarts pagination after a failed portfolio filter change", async ({
  page,
}) => {
  await page.route(`${API}.get_bootstrap`, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.message.portfolios = [
      { name: "PORTFOLIO-A", label: "Portfolio A" },
      { name: "PORTFOLIO-B", label: "Portfolio B" },
    ];
    await route.fulfill({ response, json: payload });
  });

  const portfolioBOffsets: number[] = [];
  await page.route(`${API}.get_transactions?*`, async (route) => {
    const parameters = new URL(route.request().url()).searchParams;
    const portfolio = parameters.get("portfolio") || "PORTFOLIO-A";
    const start = Number(parameters.get("start") || 0);
    if (portfolio === "PORTFOLIO-B") {
      portfolioBOffsets.push(start);
      if (portfolioBOffsets.length === 1) {
        await route.fulfill({ status: 500, json: {} });
        return;
      }
    }
    await route.fulfill({
      json: {
        message: {
          data: Array.from({ length: start === 0 ? 20 : 1 }, (_, index) => ({
            name: `${portfolio}-${start + index}`,
            portfolio_name: portfolio,
            settlement_date: "2026-01-02",
            trade_date: "2026-01-01",
            transaction_type: "Purchase",
            isin: "UI-TEST-BOND-001",
            quantity_face_value: 10,
            price: 100,
          })),
          pagination: { start, page_length: 20, has_more: start === 0 },
        },
      },
    });
  });

  await page.goto("/bond-investor/transactions");
  const portfolioFilter = page.getByRole("combobox", {
    name: "Portfolio Name",
    exact: true,
  });
  await portfolioFilter.selectOption("PORTFOLIO-A");
  const rows = page.getByTestId("transaction-row");
  await expect(rows).toHaveCount(20);
  await expect(rows.first()).toContainText("PORTFOLIO-A");
  await expect(
    page.getByRole("button", { name: "Load More", exact: true })
  ).toBeVisible();

  await portfolioFilter.selectOption("PORTFOLIO-B");
  await expect(page.getByRole("alert")).toContainText(
    "Transactions could not be loaded"
  );
  await expect(rows).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Load More", exact: true })
  ).toHaveCount(0);

  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(rows).toHaveCount(20);
  await expect(rows.first()).toContainText("PORTFOLIO-B");
  await page.getByRole("button", { name: "Load More", exact: true }).click();
  await expect(rows).toHaveCount(21);
  await expect(rows.filter({ hasText: "PORTFOLIO-A" })).toHaveCount(0);
  expect(portfolioBOffsets).toEqual([0, 0, 20]);
});

test("shows an accessible yield value for a single market date", async ({
  page,
}) => {
  await page.goto("/bond-investor/yield-comparison");
  await expect(page.getByTestId("yield-comparison-initial")).toBeVisible();
  await page.getByLabel("From Date").fill("2095-01-01");
  await page.getByLabel("To Date").fill("2095-01-01");
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const point = page
    .getByTestId("yield-comparison-chart")
    .getByLabel(
      "01 Jan 2095, UI-TEST-BOND-001, USD, Market Price 102.500, Future XIRR 7.000%",
      { exact: true }
    );
  await expect(point).toBeVisible();
  await point.focus();
  await expect(point).toBeFocused();
});

function marketPrice(isin: string, futureXirr: number | null) {
  return {
    isin,
    currency: "USD",
    principal_factor: 1,
    market_price: 100,
    future_xirr: futureXirr,
    weighted_avg_repayment_date: "2029-01-01",
    weighted_avg_repayment_years: 3,
    maturity_date: "2029-01-01",
  };
}
