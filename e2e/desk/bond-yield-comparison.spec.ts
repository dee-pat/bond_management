import { expect, test } from "@playwright/test";

import { installYieldComparisonFixtures, yieldBondIsins } from "./fixtures";
import {
  captureClipboard,
  readClipboardCalls,
  type DeskTestWindow,
} from "./helpers/frappe";

const comparisonRoute =
  "/desk/query-report/Bond%20Yield%20Comparison?from_date=2025-01-01&to_date=2025-03-01";

test.beforeEach(async ({ page }) => {
  await installYieldComparisonFixtures(page);
});

test("compares selected bonds and assigns one colour per currency", async ({
  page,
}) => {
  await page.goto(comparisonRoute);

  await expect(
    page.locator('.page-form .multiselect-list[data-fieldname="bonds"]')
  ).toHaveCount(0);
  const bondCheckboxes = page.locator(
    "[data-bond-yield-selection] .bond-yield-checkbox"
  );
  await expect(bondCheckboxes).toHaveCount(3);
  for (const checkbox of await bondCheckboxes.all()) {
    await expect(checkbox).toBeVisible();
    await expect(checkbox).toBeChecked();
  }

  const selectAll = page.locator("[data-bond-yield-select-all]");
  await expect(selectAll).toBeChecked();
  const currencySelection = page.locator("[data-bond-yield-selection] tbody");
  await expect(currencySelection).toContainText("USD");
  await expect(currencySelection).toContainText("KES");
  await expect(
    page.locator('[data-chart-mode="gap-aware"] [data-bond-yield-y-tick]')
  ).toHaveText(["0%", "5%", "10%", "15%"]);

  const initialChart = await page.evaluate(() => {
    const chart = (window as DeskTestWindow).frappe.query_report.chart;
    if (!chart) {
      throw new Error("Yield comparison chart did not load");
    }
    return {
      title: chart.title,
      labels: chart.data.labels,
      datasets: chart.data.datasets.map((dataset) => ({
        name: dataset.name,
        values: dataset.values,
      })),
      colors: chart.colors,
    };
  });
  expect(initialChart.title).toBe("Future XIRR (%) by Year");
  expect(initialChart.labels).toEqual(["2025", "2025", "2025"]);
  expect(initialChart.datasets.map((dataset) => dataset.name)).toEqual([
    yieldBondIsins.kes,
    yieldBondIsins.usd,
    yieldBondIsins.usdTwo,
  ]);
  expect(
    initialChart.datasets.every((dataset) => !dataset.values.includes(0))
  ).toBe(true);
  expect(initialChart.colors[0]).not.toBe(initialChart.colors[1]);
  expect(initialChart.colors[1]).toBe(initialChart.colors[2]);
  await expect(page.locator(".chart-wrapper .chart-legend")).toHaveCount(0);

  const kesCheckbox = page.locator(
    `[data-bond-yield-selection] input[data-bond-yield-isin="${yieldBondIsins.kes}"]`
  );
  await kesCheckbox.uncheck();
  await expect(kesCheckbox).not.toBeChecked();
  await expect(selectAll).not.toBeChecked();
  const partialChart = await page.evaluate(() => {
    const chart = (window as DeskTestWindow).frappe.query_report.chart;
    if (!chart) {
      throw new Error("Yield comparison chart did not load");
    }
    return chart.data.datasets.map((dataset) => dataset.name);
  });
  expect(partialChart).toEqual([yieldBondIsins.usd, yieldBondIsins.usdTwo]);

  await kesCheckbox.check();
  await expect(selectAll).toBeChecked();
  const restoredChart = await page.evaluate(() => {
    const chart = (window as DeskTestWindow).frappe.query_report.chart;
    if (!chart) {
      throw new Error("Yield comparison chart did not load");
    }
    return {
      labels: chart.data.labels,
      names: chart.data.datasets.map((dataset) => dataset.name),
      colors: chart.colors,
    };
  });
  expect(restoredChart.labels).toEqual(["2025", "2025", "2025"]);
  expect(restoredChart.names).toEqual([
    yieldBondIsins.kes,
    yieldBondIsins.usd,
    yieldBondIsins.usdTwo,
  ]);
  expect(restoredChart.colors[0]).not.toBe(restoredChart.colors[1]);
  expect(restoredChart.colors[1]).toBe(restoredChart.colors[2]);
  await expect(
    page.locator("[data-bond-yield-selection] .bond-yield-selection-summary")
  ).toContainText("3 of 3 bonds selected");

  await captureClipboard(page);
  await page.locator("[data-copy-audit-data]").click();
  const clipboardCalls = await readClipboardCalls(page);
  expect(clipboardCalls).toHaveLength(1);
  expect(clipboardCalls[0][0]).toContain("Future XIRR");
  await expect(page.locator(".report-wrapper")).toBeHidden();

  await selectAll.uncheck();
  await expect(
    page.locator("[data-bond-yield-selection] .bond-yield-checkbox:checked")
  ).toHaveCount(0);
  await expect(selectAll).not.toBeChecked();
  await expect(page.locator(".chart-wrapper")).toContainText(
    "Select one or more bonds to display their stored Future XIRR."
  );
  await selectAll.check();
  await expect(selectAll).toBeChecked();
});

test("keeps the chart visible when more than five snapshots do not overlap", async ({
  page,
}) => {
  await page.goto(
    "/desk/query-report/Bond%20Yield%20Comparison?from_date=2025-04-01&to_date=2025-11-01"
  );

  const chart = page.locator('.chart-wrapper [data-chart-mode="gap-aware"]');
  await expect(chart).toBeVisible();
  await expect(page.locator(".chart-wrapper .chart-data-point")).toHaveCount(0);
  const lines = page.locator(".chart-wrapper .chart-data-line");
  await expect(lines).toHaveCount(6);
  await expect(page.locator(".chart-wrapper .chart-legend")).toHaveCount(0);
  await expect(lines.locator("title").first()).toContainText(
    yieldBondIsins.noOverlap
  );

  const firstLine = lines.first();
  const hoverCoordinates = await firstLine.evaluate((line) => {
    const svg = line.closest("svg");
    if (!svg) {
      throw new Error("Yield comparison line has no SVG parent");
    }
    const bounds = svg.getBoundingClientRect();
    return {
      clientX: bounds.left + (bounds.width * 82) / 1000,
      clientY: bounds.top + bounds.height / 2,
    };
  });
  await firstLine.dispatchEvent("mousemove", hoverCoordinates);
  await expect(page.locator("[data-bond-yield-hover-tooltip]")).toBeVisible();
  await expect(page.locator("[data-bond-yield-hover-isin]")).toHaveText(
    yieldBondIsins.noOverlap
  );
  await expect(page.locator("[data-bond-yield-hover-value]")).toContainText(
    "8.75%"
  );
  await expect(
    page.locator("[data-bond-yield-hover-tooltip] [data-bond-yield-hover-isin]")
  ).toHaveCount(1);

  const checkboxes = page.locator(
    "[data-bond-yield-selection] .bond-yield-checkbox"
  );
  await expect(checkboxes).toHaveCount(6);
  for (const checkbox of await checkboxes.all()) {
    await expect(checkbox).toBeChecked();
  }
  const gaps = await page.evaluate(() => {
    const chart = (window as DeskTestWindow).frappe.query_report.chart;
    if (!chart) {
      throw new Error("Yield comparison chart did not load");
    }
    return chart.data.datasets.map((dataset) => dataset.values);
  });
  expect(gaps).toHaveLength(6);
  expect(gaps[0]).toContain(null);
  expect(gaps[0]).not.toContain(0);

  await page
    .locator(
      `[data-bond-yield-selection] input[data-bond-yield-isin="${yieldBondIsins.noOverlap}"]`
    )
    .uncheck();
  await expect(chart).toBeVisible();
  await expect(lines).toHaveCount(5);
});

test("removes comparison controls when navigating to another report", async ({
  page,
}) => {
  await page.goto(comparisonRoute);
  const performanceReport = page.waitForResponse((response) => {
    if (!response.url().includes("frappe.desk.query_report.run")) {
      return false;
    }
    return (
      new URL(response.url()).searchParams.get("report_name") ===
      "Portfolio Performance"
    );
  });

  await page.evaluate(() => {
    (window as DeskTestWindow).frappe.set_route(
      "query-report",
      "Portfolio Performance",
      { portfolio: "TEST-PORTFOLIO", valuation_date: "2025-12-31" }
    );
  });
  await performanceReport;

  await expect(page.locator(".navbar-breadcrumbs")).toContainText(
    "Portfolio Performance"
  );
  await expect(page.locator("[data-bond-yield-selection]")).toHaveCount(0);
  await expect(page.locator("[data-bond-yield-audit]")).toHaveCount(0);
});
