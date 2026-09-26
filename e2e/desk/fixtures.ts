import type { Page } from "@playwright/test";

export const administratorStorageState = "e2e/.auth/administrator.json";

export const yieldBondIsins = {
  usd: "TEST-BOND-USD",
  usdTwo: "TEST-BOND-USD-TWO",
  kes: "TEST-BOND-KES",
  noOverlap: "TEST-BOND-NO-OVERLAP",
  noOverlapTwo: "TEST-BOND-NO-OVERLAP-TWO",
  noOverlapThree: "TEST-BOND-NO-OVERLAP-THREE",
  noOverlapFour: "TEST-BOND-NO-OVERLAP-FOUR",
  noOverlapFive: "TEST-BOND-NO-OVERLAP-FIVE",
  noOverlapSix: "TEST-BOND-NO-OVERLAP-SIX",
} as const;

interface YieldRow {
  date: string;
  isin: string;
  currency: string;
  market_price: number;
  future_xirr: number;
}

const yieldRows: YieldRow[] = [
  {
    date: "2025-01-01",
    isin: yieldBondIsins.usd,
    currency: "USD",
    market_price: 99,
    future_xirr: 8.25,
  },
  {
    date: "2025-01-01",
    isin: yieldBondIsins.usdTwo,
    currency: "USD",
    market_price: 100,
    future_xirr: 8.75,
  },
  {
    date: "2025-01-01",
    isin: yieldBondIsins.kes,
    currency: "KES",
    market_price: 101,
    future_xirr: 11.5,
  },
  {
    date: "2025-02-01",
    isin: yieldBondIsins.usd,
    currency: "USD",
    market_price: 98,
    future_xirr: 8.5,
  },
  {
    date: "2025-02-01",
    isin: yieldBondIsins.usdTwo,
    currency: "USD",
    market_price: 99,
    future_xirr: 9,
  },
  {
    date: "2025-02-01",
    isin: yieldBondIsins.kes,
    currency: "KES",
    market_price: 100,
    future_xirr: 11.75,
  },
  {
    date: "2025-03-01",
    isin: yieldBondIsins.usd,
    currency: "USD",
    market_price: 97,
    future_xirr: 8.75,
  },
  ...[
    [yieldBondIsins.noOverlap, "USD", "2025-04-01", "2025-06-01", 8.75, 9.25],
    [
      yieldBondIsins.noOverlapTwo,
      "KES",
      "2025-05-01",
      "2025-07-01",
      11.5,
      11.75,
    ],
    [
      yieldBondIsins.noOverlapThree,
      "EUR",
      "2025-06-01",
      "2025-08-01",
      9.5,
      9.75,
    ],
    [
      yieldBondIsins.noOverlapFour,
      "GBP",
      "2025-07-01",
      "2025-09-01",
      10.5,
      10.75,
    ],
    [
      yieldBondIsins.noOverlapFive,
      "JPY",
      "2025-08-01",
      "2025-10-01",
      12.5,
      12.75,
    ],
    [
      yieldBondIsins.noOverlapSix,
      "ZAR",
      "2025-09-01",
      "2025-11-01",
      13.5,
      13.75,
    ],
  ].flatMap(([isin, currency, firstDate, lastDate, firstYield, lastYield]) => [
    {
      date: String(firstDate),
      isin: String(isin),
      currency: String(currency),
      market_price: 101,
      future_xirr: Number(firstYield),
    },
    {
      date: String(lastDate),
      isin: String(isin),
      currency: String(currency),
      market_price: 100,
      future_xirr: Number(lastYield),
    },
  ]),
];

export async function installYieldComparisonFixtures(
  page: Page
): Promise<void> {
  await page.route(
    "**/api/method/frappe.desk.search.search_link*",
    async (route) => {
      const url = new URL(route.request().url());
      const searchText = (url.searchParams.get("txt") ?? "").toLowerCase();
      const options = Object.values(yieldBondIsins)
        .filter((isin) => isin.toLowerCase().includes(searchText))
        .map((value) => ({ value, description: "Test bond" }));
      await route.fulfill({ json: { message: options } });
    }
  );
  await page.route(
    "**/api/method/frappe.client.validate_link_and_fetch*",
    async (route) => {
      await route.fulfill({ json: { message: { name: "TEST-PORTFOLIO" } } });
    }
  );
  await page.route(
    "**/api/method/frappe.desk.query_report.run*",
    async (route) => {
      const url = new URL(route.request().url());
      if (url.searchParams.get("report_name") === "Portfolio Performance") {
        await route.fulfill({
          json: {
            message: {
              columns: [
                { label: "ISIN", fieldname: "isin", fieldtype: "Data" },
              ],
              result: [{ isin: yieldBondIsins.usd }],
              execution_time: 0.01,
            },
          },
        });
        return;
      }

      const filters = parseFilters(url.searchParams.get("filters"));
      const selectedBonds = filters.bonds ?? [];
      const rows = yieldRows.filter((row) => {
        if (selectedBonds.length && !selectedBonds.includes(row.isin)) {
          return false;
        }
        if (filters.from_date && row.date < filters.from_date) {
          return false;
        }
        if (filters.to_date && row.date > filters.to_date) {
          return false;
        }
        return true;
      });

      await route.fulfill({
        json: {
          message: {
            columns: [
              { label: "Date", fieldname: "date", fieldtype: "Date" },
              { label: "ISIN", fieldname: "isin", fieldtype: "Link" },
              { label: "CCY", fieldname: "currency", fieldtype: "Data" },
              {
                label: "Market Price",
                fieldname: "market_price",
                fieldtype: "Float",
              },
              {
                label: "Future XIRR",
                fieldname: "future_xirr",
                fieldtype: "Percent",
              },
            ],
            result: rows,
            execution_time: 0.01,
          },
        },
      });
    }
  );
}

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

interface Filters {
  bonds: string[];
  from_date?: string;
  to_date?: string;
}

function parseFilters(value: string | null): Filters {
  if (!value) {
    return { bonds: [] };
  }
  return JSON.parse(value) as Filters;
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
    {
      label: "Expected Coupons (Next Year)",
      fieldname: "expected_coupons_next_year",
      fieldtype: "Currency",
      options: "currency",
      width: 190,
    },
  ],
  result: [
    {
      isin: "TEST-BOND",
      currency: "USD",
      xirr: 12.5,
      xirr_usd: 8.75,
      future_xirr: 7.25,
      expected_coupons_next_year: 70,
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
    {
      label: "Expected Coupons (Next Year)",
      fieldname: "expected_coupons_next_year",
      fieldtype: "Currency",
      options: "currency",
      width: 190,
    },
  ],
  result: [
    {
      isin: "TEST-BOND",
      market_value: 100,
      xirr: 12.5,
      expected_coupons_next_year: 70,
    },
  ],
  execution_time: 0.01,
};
