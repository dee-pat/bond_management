import type { Page } from "@playwright/test";

export const administratorStorageState = "e2e/.auth/administrator.json";

export async function installPortfolioPerformanceFixtures(
  page: Page,
  variant: "copy-cashflows" | "usd-only"
): Promise<void> {
  await page.route(
    "**/api/method/frappe.client.validate_link_and_fetch*",
    async (route) => {
      await route.fulfill({ json: { message: { name: "TEST-PORTFOLIO" } } });
    }
  );
  await page.route(
    "**/api/method/frappe.desk.query_report.run*",
    async (route) => {
      const response =
        variant === "copy-cashflows" ? copyCashflowsReport : usdOnlyReport;
      await route.fulfill({ json: { message: response } });
    }
  );

  if (variant === "copy-cashflows") {
    await page.route(
      "**/api/method/bond_management.bond_management.report.portfolio_performance.portfolio_performance.get_xirr_cashflows",
      async (route) => {
        await route.fulfill({
          json: {
            message: [
              {
                isin: "=TEST\tBOND\nALERT",
                transaction_type: "+purchase",
                date: "2025-12-31",
                currency: "@USD",
                amount: -1000,
                quantity: 10,
                rate: -100,
              },
            ],
          },
        });
      }
    );
  }
}

const copyCashflowsReport = {
  columns: [
    { label: "ISIN", fieldname: "isin", fieldtype: "Data", width: 160 },
    {
      label: "XIRR",
      fieldname: "xirr",
      fieldtype: "Percent",
      precision: 3,
      width: 100,
    },
    {
      label: "XIRR (USD)",
      fieldname: "xirr_usd",
      fieldtype: "Percent",
      precision: 3,
      width: 120,
    },
    {
      label: "Future XIRR",
      fieldname: "future_xirr",
      fieldtype: "Percent",
      precision: 3,
      width: 120,
    },
    { label: "Next Coupon Date", fieldname: "next_coupon_date", fieldtype: "Date", options: "currency", width: 145 },
    { label: "Next Coupon Amount", fieldname: "next_coupon_amount", fieldtype: "Currency", options: "currency", width: 145 },
    { label: "Second Coupon Date", fieldname: "second_coupon_date", fieldtype: "Date", options: "currency", width: 145 },
    { label: "Second Coupon Amount", fieldname: "second_coupon_amount", fieldtype: "Currency", options: "currency", width: 145 },
  ],
  result: [
    {
      isin: "TEST-BOND",
      currency: "USD",
      xirr: 12.5,
      xirr_usd: 8.75,
      future_xirr: 7.25,
      next_coupon_date: "2026-01-01",
      next_coupon_amount: 35,
      second_coupon_date: "2026-07-01",
      second_coupon_amount: 35,
      has_past_cashflows: true,
      has_future_cashflows: true,
    },
    {
      isin: "UNDEFINED-XIRR",
      currency: "USD",
      xirr: null,
      xirr_usd: null,
      future_xirr: null,
      has_past_cashflows: true,
      has_future_cashflows: true,
    },
    {
      isin: "CLOSED-BOND",
      currency: "USD",
      xirr: 0,
      xirr_usd: 0,
      future_xirr: null,
      has_past_cashflows: true,
      has_future_cashflows: false,
    },
    {
      isin: "TOTAL",
      currency: null,
      xirr: null,
      xirr_usd: null,
      future_xirr: null,
      has_past_cashflows: true,
      has_future_cashflows: true,
    },
  ],
  execution_time: 0.01,
};

const usdOnlyReport = {
  columns: [
    { label: "ISIN", fieldname: "isin", fieldtype: "Data", width: 160 },
    {
      label: "Market Value",
      fieldname: "market_value",
      fieldtype: "Currency",
      width: 135,
    },
    { label: "XIRR", fieldname: "xirr", fieldtype: "Percent", width: 80 },
    { label: "Next Coupon Date", fieldname: "next_coupon_date", fieldtype: "Date", options: "currency", width: 145 },
    { label: "Next Coupon Amount", fieldname: "next_coupon_amount", fieldtype: "Currency", options: "currency", width: 145 },
    { label: "Second Coupon Date", fieldname: "second_coupon_date", fieldtype: "Date", options: "currency", width: 145 },
    { label: "Second Coupon Amount", fieldname: "second_coupon_amount", fieldtype: "Currency", options: "currency", width: 145 },
  ],
  result: [
    {
      isin: "TEST-BOND",
      market_value: 100,
      xirr: 12.5,
      next_coupon_date: "2026-01-01",
      next_coupon_amount: 35,
      second_coupon_date: "2026-07-01",
      second_coupon_amount: 35,
    },
  ],
  execution_time: 0.01,
};
