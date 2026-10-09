import { expect, test } from "@playwright/test";

import { selectFrappeOption } from "./helpers/controls";

const PORTFOLIO = "UI Test Portfolio";

test("runs interest difference for the selected portfolio", async ({
  page,
}) => {
  await page.goto("/bond-investor/interest-difference");

  await expect(
    page.getByRole("heading", { name: "Interest Difference" }),
  ).toBeVisible();
  await expect(page.getByTestId("interest-difference-initial")).toBeVisible();
  await selectFrappeOption(page, "Portfolio (required)", PORTFOLIO);
  await page.getByRole("button", { name: "Run", exact: true }).click();

  const table = page.getByTestId("interest-difference-table");
  await expect(table).toBeVisible();
  const headers = table.getByRole("columnheader");
  await expect(headers).toHaveCount(9);
  const headerLabels = await headers.evaluateAll((elements) =>
    elements.map((element) => element.textContent?.trim() ?? ""),
  );
  expect(headerLabels).toContain("Difference (Days, DCC)");
  expect(headerLabels).toContain("Investor Gain + / Loss -");
  expect(headerLabels).not.toContain("Portfolio");
  expect(headerLabels).not.toContain("Transactions");
  await expect(
    page.getByTestId("interest-difference-row").first(),
  ).toBeVisible();
  await expect(page.getByTestId("interest-difference-total-row")).toBeVisible();
});
