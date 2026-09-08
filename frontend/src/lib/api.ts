import { useCall } from "frappe-ui";

import type {
	BondDetailResponse,
	BondPage,
	ExchangeRateDetailResponse,
	ExchangeRatePage,
	InvestorBootstrap,
	MarketDateDetailResponse,
	MarketDatePage,
	SortOrder,
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

type InvestorApiParameters = Record<string, string | number | undefined>;

export class InvestorApiError extends Error {
	status: number;

	constructor(status: number) {
		super("Investor API request failed");
		this.name = "InvestorApiError";
		this.status = status;
	}
}

interface InvestorRequest<T> {
	request: (parameters?: InvestorApiParameters) => Promise<T>;
}

function useInvestorRequest<T>(method: string): InvestorRequest<T> {
	const call = useCall<T, InvestorApiParameters>({
		url: `${INVESTOR_API_URL}.${method}`,
		immediate: false,
	});

	async function request(parameters: InvestorApiParameters = {}): Promise<T> {
		try {
			const response = await call.submit(parameters);
			if (response === null) {
				throw toInvestorApiError(call.error);
			}
			return response;
		} catch (caughtError) {
			if (caughtError instanceof InvestorApiError) {
				throw caughtError;
			}
			throw toInvestorApiError(caughtError);
		}
	}

	return { request };
}

function toInvestorApiError(caughtError: unknown): InvestorApiError {
	const errorType =
		caughtError && typeof caughtError === "object" && "type" in caughtError
			? String(caughtError.type)
			: "";
	const errorMessage =
		caughtError && typeof caughtError === "object" && "message" in caughtError
			? String(caughtError.message)
			: String(caughtError ?? "");
	const normalizedType = `${errorType} ${errorMessage}`.toLowerCase();
	if (normalizedType.includes("authentication")) {
		return new InvestorApiError(401);
	}
	if (normalizedType.includes("permission") || normalizedType.includes("forbidden")) {
		// Frappe's v1 dispatcher rejects Guest before the investor endpoint can
		// raise its AuthenticationError. Keep session-expiry redirects distinct
		// from an authenticated user's document-level permission denial.
		if (typeof document !== "undefined" && document.cookie.includes("user_id=Guest")) {
			return new InvestorApiError(401);
		}
		return new InvestorApiError(403);
	}
	return new InvestorApiError(500);
}

export function useInvestorApi() {
	const bootstrap = useInvestorRequest<InvestorBootstrap>("get_bootstrap");
	const transactions = useInvestorRequest<TransactionPage>("get_transactions");
	const transaction = useInvestorRequest<TransactionDetailResponse>("get_transaction");
	const statements = useInvestorRequest<StatementPage>("get_statements");
	const statement = useInvestorRequest<StatementDetailResponse>("get_statement");
	const bonds = useInvestorRequest<BondPage>("get_bonds");
	const bond = useInvestorRequest<BondDetailResponse>("get_bond");
	const marketDates = useInvestorRequest<MarketDatePage>("get_market_dates");
	const marketDate = useInvestorRequest<MarketDateDetailResponse>("get_market_date");
	const exchangeRates = useInvestorRequest<ExchangeRatePage>("get_exchange_rates");
	const exchangeRate = useInvestorRequest<ExchangeRateDetailResponse>("get_exchange_rate");
	const portfolioPerformance = useInvestorRequest<PortfolioPerformanceResponse>(
		"get_portfolio_performance"
	);
	const portfolioPerformanceCashflows = useInvestorRequest<PerformanceCashflowsResponse>(
		"get_portfolio_performance_cashflows"
	);
	const bondYieldComparison = useInvestorRequest<BondYieldComparisonResponse>(
		"get_bond_yield_comparison"
	);
	const yieldComparisonDefaults = useInvestorRequest<YieldComparisonDefaultsResponse>(
		"get_yield_comparison_defaults"
	);

	return {
		fetchBootstrap: () => bootstrap.request(),
		fetchTransactions: (options: {
			portfolio?: string;
			start?: number;
			pageLength?: number;
			sortBy?: string;
			sortOrder?: SortOrder;
			filterField?: string;
			filterValue?: string;
		}) =>
			transactions.request({
				portfolio: options.portfolio,
				start: options.start,
				page_length: options.pageLength,
				sort_by: options.sortBy,
				sort_order: options.sortOrder,
				filter_field: options.filterField,
				filter_value: options.filterValue,
			}),
		fetchTransaction: (name: string) => transaction.request({ name }),
		fetchStatements: (options: {
			portfolio?: string;
			reconciliationStatus?: string;
			start?: number;
			pageLength?: number;
			sortBy?: string;
			sortOrder?: SortOrder;
			filterField?: string;
			filterValue?: string;
		}) =>
			statements.request({
				portfolio: options.portfolio,
				reconciliation_status: options.reconciliationStatus,
				start: options.start,
				page_length: options.pageLength,
				sort_by: options.sortBy,
				sort_order: options.sortOrder,
				filter_field: options.filterField,
				filter_value: options.filterValue,
			}),
		fetchStatement: (name: string) => statement.request({ name }),
		fetchBonds: (options: {
			start?: number;
			pageLength?: number;
			sortBy?: string;
			sortOrder?: SortOrder;
			filterField?: string;
			filterValue?: string;
		}) =>
			bonds.request({
				start: options.start,
				page_length: options.pageLength,
				sort_by: options.sortBy,
				sort_order: options.sortOrder,
				filter_field: options.filterField,
				filter_value: options.filterValue,
			}),
		fetchBond: (name: string) => bond.request({ name }),
		fetchMarketDates: (options: {
			start?: number;
			pageLength?: number;
			sortBy?: string;
			sortOrder?: SortOrder;
			filterField?: string;
			filterValue?: string;
		}) =>
			marketDates.request({
				start: options.start,
				page_length: options.pageLength,
				sort_by: options.sortBy,
				sort_order: options.sortOrder,
				filter_field: options.filterField,
				filter_value: options.filterValue,
			}),
		fetchMarketDate: (name: string) => marketDate.request({ name }),
		fetchExchangeRates: (options: {
			start?: number;
			pageLength?: number;
			sortBy?: string;
			sortOrder?: SortOrder;
			filterField?: string;
			filterValue?: string;
		}) =>
			exchangeRates.request({
				start: options.start,
				page_length: options.pageLength,
				sort_by: options.sortBy,
				sort_order: options.sortOrder,
				filter_field: options.filterField,
				filter_value: options.filterValue,
			}),
		fetchExchangeRate: (name: string) => exchangeRate.request({ name }),
		fetchPortfolioPerformance: (options: {
			portfolio: string;
			valuationDate: string;
		}) =>
			portfolioPerformance.request({
				portfolio: options.portfolio,
				valuation_date: options.valuationDate,
			}),
		fetchPortfolioPerformanceCashflows: (options: {
			portfolio: string;
			valuationDate: string;
			isin: string;
			xirrType: XirrType;
			cashflowCurrency: CashflowCurrency;
		}) =>
			portfolioPerformanceCashflows.request({
				portfolio: options.portfolio,
				valuation_date: options.valuationDate,
				isin: options.isin,
				xirr_type: options.xirrType,
				cashflow_currency: options.cashflowCurrency,
			}),
		fetchBondYieldComparison: (options: { fromDate?: string; toDate?: string }) =>
			bondYieldComparison.request({
				from_date: options.fromDate,
				to_date: options.toDate,
			}),
		fetchYieldComparisonDefaults: () => yieldComparisonDefaults.request(),
	};
}

export function redirectToLogin(): void {
	const target = `${window.location.pathname}${window.location.search}${window.location.hash}`;
	window.location.assign(`/login?redirect-to=${encodeURIComponent(target)}`);
}
