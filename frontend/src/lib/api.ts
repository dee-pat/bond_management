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
	InterestDifferenceResponse,
	PerformanceCashflowsResponse,
	PortfolioPerformanceResponse,
	YieldComparisonDefaultsResponse,
	XirrType,
} from "../report-types";

const INVESTOR_API_URL =
	"/api/method/bond_management.bond_management.api.investor";

type InvestorApiParameters = Record<string, string | number | undefined>;

interface ListOptions {
	start?: number;
	pageLength?: number;
	sortBy?: string;
	sortOrder?: SortOrder;
	filterField?: string;
	filterValue?: string;
}

interface PortfolioListOptions extends ListOptions {
	portfolio?: string;
}

interface StatementListOptions extends PortfolioListOptions {
	reconciliationStatus?: string;
}

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

interface InvestorResponseBody {
	data?: unknown;
	exc_type?: unknown;
}

function useInvestorRequest<T>(method: string): InvestorRequest<T> {
	const url = `${INVESTOR_API_URL}.${method}`;

	// Each request is its own fetch, so a failure can never return another
	// request's data. frappe-ui's useCall is not used: it drops the HTTP status,
	// and v1 `/api/method` errors carry only `exc_type`, so a 401, or any error
	// over HTTP/2 (no status text), could not be told apart from a server error.
	async function request(parameters: InvestorApiParameters = {}): Promise<T> {
		let response: Response;
		try {
			response = await fetch(withQuery(url, parameters), { headers: requestHeaders() });
		} catch {
			throw new InvestorApiError(500);
		}

		const body = await readJson(response);
		if (!response.ok) {
			throw toInvestorApiError(response.status, body?.exc_type);
		}
		if (body?.data === undefined || body.data === null) {
			throw new InvestorApiError(500);
		}
		return body.data as T;
	}

	return { request };
}

function withQuery(url: string, parameters: InvestorApiParameters): string {
	const query = new URLSearchParams();
	for (const [key, value] of Object.entries(parameters)) {
		if (value !== undefined) {
			query.append(key, String(value));
		}
	}
	const queryString = query.toString();
	return queryString ? `${url}?${queryString}` : url;
}

function requestHeaders(): Record<string, string> {
	// The same headers frappe-ui sends; the site name routes the Vite dev proxy.
	const headers: Record<string, string> = {
		Accept: "application/json",
		"X-Frappe-Site-Name": window.location.hostname,
	};
	const csrfToken = window.csrf_token;
	if (csrfToken && csrfToken !== "{{ csrf_token }}") {
		headers["X-Frappe-CSRF-Token"] = csrfToken;
	}
	return headers;
}

async function readJson(response: Response): Promise<InvestorResponseBody | null> {
	try {
		const body: unknown = await response.json();
		return body && typeof body === "object" ? (body as InvestorResponseBody) : null;
	} catch {
		return null;
	}
}

function toInvestorApiError(status: number, excType: unknown): InvestorApiError {
	if (status === 401 || excType === "AuthenticationError") {
		return new InvestorApiError(401);
	}
	if (status === 403 || excType === "PermissionError") {
		// Frappe's v1 dispatcher rejects Guest with a PermissionError before the
		// investor endpoint can raise its AuthenticationError. Keep session-expiry
		// redirects distinct from an authenticated user's document-level denial.
		if (document.cookie.includes("user_id=Guest")) {
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
	const interestDifference = useInvestorRequest<InterestDifferenceResponse>(
		"get_interest_difference_by_portfolio"
	);
	const bondYieldComparison = useInvestorRequest<BondYieldComparisonResponse>(
		"get_bond_yield_comparison"
	);
	const yieldComparisonDefaults = useInvestorRequest<YieldComparisonDefaultsResponse>(
		"get_yield_comparison_defaults"
	);

	return {
		fetchBootstrap: () => bootstrap.request(),
		fetchTransactions: (options: PortfolioListOptions) =>
			transactions.request({
				portfolio: options.portfolio,
				...listParams(options),
			}),
		fetchTransaction: (name: string) => transaction.request({ name }),
		fetchStatements: (options: StatementListOptions) =>
			statements.request({
				portfolio: options.portfolio,
				reconciliation_status: options.reconciliationStatus,
				...listParams(options),
			}),
		fetchStatement: (name: string) => statement.request({ name }),
		fetchBonds: (options: ListOptions) => bonds.request(listParams(options)),
		fetchBond: (name: string) => bond.request({ name }),
		fetchMarketDates: (options: ListOptions) =>
			marketDates.request(listParams(options)),
		fetchMarketDate: (name: string) => marketDate.request({ name }),
		fetchExchangeRates: (options: ListOptions) =>
			exchangeRates.request(listParams(options)),
		fetchExchangeRate: (name: string) => exchangeRate.request({ name }),
		fetchPortfolioPerformance: (options: {
			portfolio: string;
			valuationDate: string;
		}) =>
			portfolioPerformance.request({
				portfolio: options.portfolio,
				valuation_date: options.valuationDate,
			}),
		fetchInterestDifference: (options: {
			portfolio: string;
			fromDate?: string;
			toDate?: string;
		}) =>
			interestDifference.request({
				portfolio: options.portfolio,
				from_date: options.fromDate,
				to_date: options.toDate,
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

function listParams(options: ListOptions): InvestorApiParameters {
	return {
		start: options.start,
		page_length: options.pageLength,
		sort_by: options.sortBy,
		sort_order: options.sortOrder,
		filter_field: options.filterField,
		filter_value: options.filterValue,
	};
}
