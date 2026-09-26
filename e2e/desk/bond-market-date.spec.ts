import { expect, test } from "@playwright/test";

import {
  captureClipboard,
  openDeskForm,
  readClipboardCalls,
  type DeskTestWindow,
} from "./helpers/frappe";

const marketDate = "2025-01-01";
const targetIsin = "TEST-BOND-WEIGHTED";
const referenceIsin = "TEST-BOND-REFERENCE";
const targetPrice = 99.25;
const weightedDate = "2027-01-01";

const marketData = {
  [targetIsin]: {
    currency: "KES",
    future_xirr: 8.75,
    principal_factor: 1,
    weighted_avg_repayment_date: weightedDate,
    weighted_avg_repayment_years: 2,
  },
  [referenceIsin]: {
    currency: "USD",
    future_xirr: 9.25,
    principal_factor: 1,
    weighted_avg_repayment_date: "2029-01-01",
    weighted_avg_repayment_years: 1461 / 365,
  },
};

const cashflows = [
  {
    isin: "=TEST\tBOND\nALERT",
    type: "+principal",
    date: weightedDate,
    amount: 100,
  },
  {
    isin: targetIsin,
    type: "market_price",
    date: marketDate,
    amount: -targetPrice,
  },
  {
    isin: targetIsin,
    type: "coupon",
    date: "2026-01-01",
    amount: 8.5,
  },
];

const expectedTsv = [
  "isin\ttransaction_type\tdate\tamount",
  `${targetIsin}\tmarket_price\t${marketDate}\t-${targetPrice}`,
  `${targetIsin}\tcoupon\t2026-01-01\t8.5`,
  "'=TEST BOND ALERT\t'+principal\t2027-01-01\t100",
].join("\n");

test.beforeEach(async ({ page }) => {
  await page.route(
    "**/api/method/bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_recalculated_market_data",
    async (route) => {
      const requestData = parsePostData(route.request().postData());
      const rowsValue = requestData.rows;
      const rows =
        typeof rowsValue === "string" ? JSON.parse(rowsValue) : rowsValue;
      if (!Array.isArray(rows)) {
        throw new Error("Market recalculation request did not include rows");
      }

      const result = rows.map((row) => {
        const values = marketData[row.isin as keyof typeof marketData];
        if (!values) {
          throw new Error(`No market fixture for ${String(row.isin)}`);
        }
        return { name: row.name, ...values };
      });
      await route.fulfill({ json: { message: result } });
    }
  );
  await page.route(
    "**/api/method/bond_management.bond_management.doctype.bond_market_date.bond_market_date.get_cashflows",
    async (route) => {
      await route.fulfill({ json: { message: cashflows } });
    }
  );
});

test("copies the selected bond cash flows from Future XIRR", async ({
  page,
}) => {
  await openDeskForm(page, "/desk/bond-market-date/new", "Bond Market Date");
  await captureClipboard(page);

  const recalculation = page.waitForResponse((response) =>
    response.url().includes("get_recalculated_market_data")
  );
  await page.evaluate(
    async ({ marketDate, targetIsin, targetPrice, referenceIsin }) => {
      const form = (window as DeskTestWindow).cur_frm;
      if (!form) {
        throw new Error("Bond Market Date form did not load");
      }

      form.clear_table("bond_market_prices");
      form.doc.date = marketDate;
      const target = form.add_child("bond_market_prices", {
        isin: targetIsin,
        market_price: targetPrice,
      });
      form.add_child("bond_market_prices", {
        isin: referenceIsin,
        market_price: 101,
      });
      form.refresh_field("date");
      form.refresh_field("bond_market_prices");
      await form.script_manager.trigger(
        "market_price",
        target.doctype,
        target.name
      );
    },
    { marketDate, targetIsin, targetPrice, referenceIsin }
  );
  await recalculation;

  const targetXirr = page.locator(
    `.bond-market-cashflow-copy[data-isin="${targetIsin}"]`
  );
  await expect(targetXirr).toBeVisible();
  const cashflowResponse = page.waitForResponse((response) =>
    response.url().includes("get_cashflows")
  );
  await targetXirr.click();
  const request = await cashflowResponse;
  const requestData = parsePostData(request.request().postData());

  expect(requestData).toMatchObject({
    date: marketDate,
    isin: targetIsin,
    market_price: String(targetPrice),
  });
  expect(await readClipboardCalls(page)).toEqual([
    [expectedTsv, `Copied ${cashflows.length} cash flows for ${targetIsin}`],
  ]);
});

test("renders one yield-curve line per currency", async ({ page }) => {
  await openDeskForm(page, "/desk/bond-market-date/new", "Bond Market Date");
  const recalculation = page.waitForResponse((response) =>
    response.url().includes("get_recalculated_market_data")
  );
  await page.evaluate(
    async ({ marketDate, targetIsin, targetPrice, referenceIsin }) => {
      const form = (window as DeskTestWindow).cur_frm;
      if (!form) {
        throw new Error("Bond Market Date form did not load");
      }

      form.clear_table("bond_market_prices");
      form.doc.date = marketDate;
      const target = form.add_child("bond_market_prices", {
        isin: targetIsin,
        market_price: targetPrice,
      });
      form.add_child("bond_market_prices", {
        isin: referenceIsin,
        market_price: 101,
      });
      form.refresh_field("date");
      form.refresh_field("bond_market_prices");
      await form.script_manager.trigger(
        "market_price",
        target.doctype,
        target.name
      );
    },
    { marketDate, targetIsin, targetPrice, referenceIsin }
  );
  await recalculation;

  const lines = page.locator(".bond-yield-curve polyline");
  await expect(lines).toHaveCount(2);
  const currencies = await lines.evaluateAll((elements) =>
    elements.map((line) => line.getAttribute("data-currency"))
  );
  const colors = await lines.evaluateAll((elements) =>
    elements.map((line) => line.getAttribute("stroke"))
  );
  expect(currencies).toEqual(["KES", "USD"]);
  expect(new Set(colors).size).toBe(2);
  await expect(
    page.locator('.bond-yield-legend [role="listitem"]')
  ).toHaveCount(2);
});

function parsePostData(postData: string | null): Record<string, unknown> {
  if (!postData) {
    return {};
  }

  try {
    return JSON.parse(postData) as Record<string, unknown>;
  } catch {
    return Object.fromEntries(new URLSearchParams(postData));
  }
}
