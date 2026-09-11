import { expect, test, type Route } from "@playwright/test";

const PRIMARY_BOND = "UI-TEST-BOND-001";
const GAP_BOND = "-UI-TEST-YIELD-BOND-002";
const INVESTOR_API =
  "**/api/method/bond_management.bond_management.api.investor";

test("compares persisted bond yields without mobile overflow", async ({
  page,
}) => {
  const defaultsResponse = page.waitForResponse((response) =>
    response.url().includes(".get_yield_comparison_defaults")
  );
  await page.goto("/bond-investor/yield-comparison");
  const defaults = (await (await defaultsResponse).json()) as {
    message: { filters: { from_date: string | null; to_date: string } };
  };

  await expect(page.getByTestId("yield-comparison-initial")).toBeVisible();
  await expect(page.getByLabel("From Date")).toHaveValue(
    defaults.message.filters.from_date ?? ""
  );
  await expect(page.getByLabel("To Date")).toHaveValue(
    defaults.message.filters.to_date
  );
  await page.getByLabel("From Date").fill("2095-01-01");
	await page.getByLabel("To Date").fill("2095-01-03");
	await page.getByRole("button", { name: "Run", exact: true }).click();

	await expect(page.getByTestId("yield-comparison-selector")).toHaveCount(0);

	const chart = page.getByTestId("yield-comparison-chart");
  const image = chart.getByRole("img", {
    name: "Persisted Future XIRR, By market date and bond",
  });
  await expect(image).toBeVisible();
  await expect(chart).toHaveAttribute("data-gap-count", "1");
  await expect(
    chart.getByRole("button", { name: `Hide ${PRIMARY_BOND} · USD` })
  ).toContainText(PRIMARY_BOND);
  await expect(
    chart.getByRole("button", { name: `Hide ${GAP_BOND} · KES` })
  ).toContainText(GAP_BOND);
  await expect(chart).toHaveAccessibleDescription(
    new RegExp(
      `03 Jan 2095, ${GAP_BOND}, KES, Market Price 100.750, Future XIRR 9.625%`
    )
  );
  await expect(
    chart.getByTestId("yield-comparison-chart-description").filter({
      hasText: `03 Jan 2095, ${GAP_BOND}, KES, Market Price 100.750, Future XIRR 9.625%`,
    })
  ).toContainText("Future XIRR 9.625%");
  await expect(page.locator("table")).toHaveCount(0);

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});

test("keeps the mobile yield chart usable with a large legend", async ({
  page,
}) => {
  await page.route(
    `${INVESTOR_API}.get_bond_yield_comparison*`,
    async (route) => {
      await fulfillJson(route, largeYieldComparisonResponse());
    }
  );

  await page.goto("/bond-investor/yield-comparison");
  await expect(page.getByTestId("yield-comparison-initial")).toBeVisible();
  await page.getByLabel("From Date").fill("2095-01-01");
  await page.getByLabel("To Date").fill("2095-01-01");
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const chart = page.getByTestId("yield-comparison-chart");
  const image = chart.getByRole("img", {
    name: "Persisted Future XIRR, By market date and bond",
  });
  await expect(image).toBeVisible();

  const legend = chart.locator('[data-slot="chart-legend"]');
  const legendButtons = legend.getByRole("button");
  await expect(legendButtons).toHaveCount(30);
  await legendButtons.last().scrollIntoViewIfNeeded();
  await expect(legendButtons.last()).toBeVisible();

  const plotBox = await chart.locator('[data-slot="chart-plot"]').boundingBox();
  expect(plotBox).not.toBeNull();
  expect(plotBox!.height).toBeGreaterThan(0);
  await expect(page.locator("table")).toHaveCount(0);
});

async function fulfillJson(route: Route, payload: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

function largeYieldComparisonResponse(): object {
  const report = {
    filters: { from_date: "2095-01-01", to_date: "2095-01-01" },
    columns: [
      column("date", "Date", "Date"),
      column("isin", "ISIN", "Link"),
      column("currency", "CCY", "Data"),
      column("market_price", "Market Price", "Float", 3),
      column("future_xirr", "Future XIRR", "Percent", 3),
    ],
    rows: Array.from({ length: 30 }, (_, index) => ({
      date: "2095-01-01",
      isin: `MOBILE-LEGEND-${String(index + 1).padStart(2, "0")}`,
      currency: "USD",
      market_price: 100 + index,
      future_xirr: index + 1,
    })),
    chart: {
      x_field: "date",
      value_field: "future_xirr",
      series_field: "isin",
      gap_policy: "preserve",
    },
  };
  return { message: { report }, data: { report } };
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
