import type {
  BondDetailResponse,
  BondPage,
  ExchangeRateDetailResponse,
  ExchangeRatePage,
  InvestorBootstrap,
  MarketDateDetailResponse,
  MarketDatePage,
  StatementDetailResponse,
  StatementPage,
  TransactionDetailResponse,
  TransactionPage,
} from "../types";
import type {
  BondYieldComparisonResponse,
  CashflowCurrency,
  PerformanceCashflowsResponse,
  PortfolioPerformanceResponse,
  YieldComparisonDefaultsResponse,
  XirrType,
} from "../report-types";

const INVESTOR_API_URL =
  "/api/method/bond_management.bond_management.api.investor";

export class InvestorApiError extends Error {
  status: number;

  constructor(status: number) {
    super("Investor API request failed");
    this.name = "InvestorApiError";
    this.status = status;
  }
}

export async function fetchBootstrap(): Promise<InvestorBootstrap> {
  return requestInvestorApi<InvestorBootstrap>("get_bootstrap");
}

export async function fetchTransactions(options: {
  portfolio?: string;
  start?: number;
  pageLength?: number;
}): Promise<TransactionPage> {
  return requestInvestorApi<TransactionPage>("get_transactions", {
    portfolio: options.portfolio,
    start: options.start,
    page_length: options.pageLength,
  });
}

export async function fetchTransaction(
  name: string
): Promise<TransactionDetailResponse> {
  return requestInvestorApi<TransactionDetailResponse>("get_transaction", {
    name,
  });
}

export async function fetchStatements(options: {
  portfolio?: string;
  reconciliationStatus?: string;
  start?: number;
  pageLength?: number;
}): Promise<StatementPage> {
  return requestInvestorApi<StatementPage>("get_statements", {
    portfolio: options.portfolio,
    reconciliation_status: options.reconciliationStatus,
    start: options.start,
    page_length: options.pageLength,
  });
}

export async function fetchStatement(
  name: string
): Promise<StatementDetailResponse> {
  return requestInvestorApi<StatementDetailResponse>("get_statement", {
    name,
  });
}

export async function fetchBonds(options: {
  start?: number;
  pageLength?: number;
}): Promise<BondPage> {
  return requestInvestorApi<BondPage>("get_bonds", {
    start: options.start,
    page_length: options.pageLength,
  });
}

export async function fetchBond(name: string): Promise<BondDetailResponse> {
  return requestInvestorApi<BondDetailResponse>("get_bond", { name });
}

export async function fetchMarketDates(options: {
  start?: number;
  pageLength?: number;
}): Promise<MarketDatePage> {
  return requestInvestorApi<MarketDatePage>("get_market_dates", {
    start: options.start,
    page_length: options.pageLength,
  });
}

export async function fetchMarketDate(
  name: string
): Promise<MarketDateDetailResponse> {
  return requestInvestorApi<MarketDateDetailResponse>("get_market_date", {
    name,
  });
}

export async function fetchExchangeRates(options: {
  start?: number;
  pageLength?: number;
}): Promise<ExchangeRatePage> {
  return requestInvestorApi<ExchangeRatePage>("get_exchange_rates", {
    start: options.start,
    page_length: options.pageLength,
  });
}

export async function fetchExchangeRate(
  name: string
): Promise<ExchangeRateDetailResponse> {
  return requestInvestorApi<ExchangeRateDetailResponse>("get_exchange_rate", {
    name,
  });
}

export async function fetchPortfolioPerformance(options: {
  portfolio: string;
  valuationDate: string;
}): Promise<PortfolioPerformanceResponse> {
  return requestInvestorApi<PortfolioPerformanceResponse>(
    "get_portfolio_performance",
    {
      portfolio: options.portfolio,
      valuation_date: options.valuationDate,
    }
  );
}

export async function fetchPortfolioPerformanceCashflows(options: {
  portfolio: string;
  valuationDate: string;
  isin: string;
  xirrType: XirrType;
  cashflowCurrency: CashflowCurrency;
}): Promise<PerformanceCashflowsResponse> {
  return requestInvestorApi<PerformanceCashflowsResponse>(
    "get_portfolio_performance_cashflows",
    {
      portfolio: options.portfolio,
      valuation_date: options.valuationDate,
      isin: options.isin,
      xirr_type: options.xirrType,
      cashflow_currency: options.cashflowCurrency,
    }
  );
}

export async function fetchBondYieldComparison(options: {
  fromDate?: string;
  toDate?: string;
}): Promise<BondYieldComparisonResponse> {
  return requestInvestorApi<BondYieldComparisonResponse>(
    "get_bond_yield_comparison",
    {
      from_date: options.fromDate,
      to_date: options.toDate,
    }
  );
}

export async function fetchYieldComparisonDefaults(): Promise<YieldComparisonDefaultsResponse> {
  return requestInvestorApi<YieldComparisonDefaultsResponse>(
    "get_yield_comparison_defaults"
  );
}

export function redirectToLogin(): void {
  const target = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  window.location.assign(`/login?redirect-to=${encodeURIComponent(target)}`);
}

async function requestInvestorApi<T>(
  method: string,
  parameters: Record<string, string | number | undefined> = {}
): Promise<T> {
  const url = new URL(`${INVESTOR_API_URL}.${method}`, window.location.origin);
  Object.entries(parameters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });

  const csrfToken = window.csrf_token;
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: csrfToken ? { "X-Frappe-CSRF-Token": csrfToken } : {},
  });

  if (!response.ok) {
    const status =
      response.status === 403 && (await investorSessionExpired())
        ? 401
        : response.status;
    throw new InvestorApiError(status);
  }

  const payload = (await response.json()) as { message?: T };
  if (!payload.message) {
    throw new InvestorApiError(502);
  }

  return payload.message;
}

async function investorSessionExpired(): Promise<boolean> {
  try {
    const response = await fetch("/bond-investor", {
      credentials: "same-origin",
      headers: { Accept: "text/html" },
    });
    return new URL(response.url).pathname === "/login";
  } catch {
    return false;
  }
}
