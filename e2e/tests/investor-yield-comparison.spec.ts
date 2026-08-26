import { expect, test } from "@playwright/test";

const PRIMARY_BOND = "UI-TEST-BOND-001";
const GAP_BOND = "-UI-TEST-YIELD-BOND-002";
const FROM_DATE = "2095-01-01";
const TO_DATE = "2095-01-03";

test("compares persisted yields, selects series, and copies sanitized audit data", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const defaultsResponse = page.waitForResponse((response) =>
    response.url().includes(".get_yield_comparison_defaults")
  );
  await page.goto("/bond-investor/yield-comparison");
  const defaults = (await (await defaultsResponse).json()) as {
    message: { filters: { from_date: string | null; to_date: string } };
  };

  await expect(
    page.getByRole("heading", { name: "Bond Yield Comparison" })
  ).toBeVisible();
  await expect(page.getByTestId("yield-comparison-initial")).toBeVisible();
  await expect(page.getByLabel("From Date")).toHaveValue(
    defaults.message.filters.from_date ?? ""
  );
  await expect(page.getByLabel("To Date")).toHaveValue(
    defaults.message.filters.to_date
  );

  await page.getByLabel("From Date").fill(FROM_DATE);
  await page.getByLabel("To Date").fill(TO_DATE);
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const selector = page.getByTestId("yield-comparison-selector");
  await expect(selector.getByLabel("Select all bonds")).toBeChecked();
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
    chart.getByRole("listitem").filter({ hasText: PRIMARY_BOND })
  ).toBeVisible();
  await expect(
    chart.getByRole("listitem").filter({ hasText: GAP_BOND })
  ).toBeVisible();
  await expect(image).toHaveAccessibleDescription(
    new RegExp(
      `01 Jan 2095, ${GAP_BOND}, KES, Market Price 99.250, Future XIRR 9.125%`
    )
  );
  await expect(image).toHaveAccessibleDescription(
    new RegExp(
      `02 Jan 2095, ${PRIMARY_BOND}, USD, Market Price 102.500, Future XIRR 7.250%`
    )
  );
  await expect(chart.locator("circle")).toHaveCount(0);
  await expect(chart.getByTestId("yield-comparison-year-tick")).toHaveText([
    "2095",
  ]);

  await selector.getByLabel(`Select ${GAP_BOND}`).uncheck();
  await expect(selector).toContainText("1 of 2 bonds selected");
  await expect(
    chart.getByRole("listitem").filter({ hasText: GAP_BOND })
  ).toHaveCount(0);
  await selector.getByLabel(`Select ${GAP_BOND}`).check();

  await page.getByRole("button", { name: "Copy audit data to Excel" }).click();
  await expect(page.getByRole("status")).toHaveText("Copied 5 audit rows.");
  const clipboard = await page.evaluate(() => navigator.clipboard.readText());
  expect(clipboard).toContain("Date\tISIN\tCCY\tMarket Price\tFuture XIRR");
  expect(clipboard).toContain(`${FROM_DATE}\t'${GAP_BOND}\tKES\t99.25\t9.125`);

  await expect(page.locator("table")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /Export|Print|Email/ })
  ).toHaveCount(0);
  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth
  );
  expect(fitsViewport).toBeTruthy();
});
