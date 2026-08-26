import { expect, test } from "@playwright/test";

const PRIMARY_BOND = "UI-TEST-BOND-001";
const GAP_BOND = "-UI-TEST-YIELD-BOND-002";

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

  const selector = page.getByTestId("yield-comparison-selector");
  await expect(selector).toContainText("2 of 2 bonds selected");
  await expect(selector.getByLabel(`Select ${PRIMARY_BOND}`)).toBeChecked();
  await expect(selector.getByLabel(`Select ${GAP_BOND}`)).toBeChecked();

  const chart = page.getByTestId("yield-comparison-chart");
  const image = chart.getByRole("img", {
    name: "Persisted Future XIRR by market date and bond",
  });
  await expect(image).toBeVisible();
  await expect(chart).toHaveAttribute("data-gap-count", "1");
  await expect(
    chart.getByRole("listitem").filter({ hasText: "USD" })
  ).toContainText(PRIMARY_BOND);
  await expect(
    chart.getByRole("listitem").filter({ hasText: "KES" })
  ).toContainText(GAP_BOND);
  await expect(image).toHaveAccessibleDescription(
    new RegExp(
      `03 Jan 2095, ${GAP_BOND}, KES, Market Price 100.750, Future XIRR 9.625%`
    )
  );
  await expect(chart.locator("circle")).toHaveCount(0);
  await expect(chart.getByTestId("yield-comparison-year-tick")).toHaveText([
    "2095",
  ]);
  await expect(page.locator("table")).toHaveCount(0);

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
