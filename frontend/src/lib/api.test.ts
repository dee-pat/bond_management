import { beforeEach, describe, expect, it, vi } from "vitest";

import { InvestorApiError, redirectToLogin, useInvestorApi } from "./api";

const METHOD_URL = "/api/method/bond_management.bond_management.api.investor";

// Frappe v1 `/api/method` errors carry `exc_type`, not frappe-ui's `errors[]`.
function v1Error(excType: string) {
	return { exc_type: excType, _server_messages: "[]" };
}

function stubFetch(status: number, body: unknown, statusText = "") {
	const fetchMock = vi.fn(
		async (_input: RequestInfo | URL, _init?: RequestInit) =>
			new Response(typeof body === "string" ? body : JSON.stringify(body), {
				status,
				statusText,
				headers: { "Content-Type": "application/json" },
			})
	);
	vi.stubGlobal("fetch", fetchMock);
	return fetchMock;
}

function stubBrowser(cookie: string, csrfToken?: string) {
	vi.stubGlobal("document", { cookie });
	vi.stubGlobal("window", {
		csrf_token: csrfToken,
		location: { hostname: "bond-management-test.localhost" },
	});
}

async function requestError(): Promise<unknown> {
	return useInvestorApi()
		.fetchBond("BOND-1")
		.then(
			() => {
				throw new Error("expected the request to fail");
			},
			(caughtError: unknown) => caughtError
		);
}

async function expectStatus(status: number): Promise<void> {
	const caughtError = await requestError();
	expect(caughtError).toBeInstanceOf(InvestorApiError);
	expect((caughtError as InvestorApiError).status).toBe(status);
}

beforeEach(() => {
	stubBrowser("user_id=investor%40example.com; sid=abc");
});

describe("InvestorApiError", () => {
	it("carries the status behind a generic message", () => {
		const error = new InvestorApiError(403);
		expect(error).toBeInstanceOf(Error);
		expect(error.name).toBe("InvestorApiError");
		expect(error.status).toBe(403);
		expect(error.message).toBe("Investor API request failed");
	});
});

describe("investor requests", () => {
	const list = {
		start: 0,
		pageLength: 20,
		sortBy: "name",
		sortOrder: "asc" as const,
		filterField: "currency",
		filterValue: "USD & KES",
	};
	const listQuery =
		"start=0&page_length=20&sort_by=name&sort_order=asc&filter_field=currency&filter_value=USD+%26+KES";
	const name = "ROW /&1";
	const nameQuery = "?name=ROW+%2F%261";
	const dates = { fromDate: "2026-01-01", toDate: "2026-06-30" };
	const dateQuery = "from_date=2026-01-01&to_date=2026-06-30";
	const portfolio = { portfolio: "PF-1", valuationDate: "2026-06-30" };
	const portfolioQuery = "portfolio=PF-1&valuation_date=2026-06-30";
	const endpoints: [string, (api: ReturnType<typeof useInvestorApi>) => Promise<unknown>, string][] = [
		["get_bootstrap", (api) => api.fetchBootstrap(), ""],
		["get_transactions", (api) => api.fetchTransactions({ ...list, portfolio: "PF-1" }),
			`?portfolio=PF-1&${listQuery}`],
		["get_transaction", (api) => api.fetchTransaction(name), nameQuery],
		["get_statements", (api) => api.fetchStatements({
			...list, portfolio: "PF-1", reconciliationStatus: "Matched",
		}), `?portfolio=PF-1&reconciliation_status=Matched&${listQuery}`],
		["get_statement", (api) => api.fetchStatement(name), nameQuery],
		["get_bonds", (api) => api.fetchBonds(list), `?${listQuery}`],
		["get_bond", (api) => api.fetchBond(name), nameQuery],
		["get_market_dates", (api) => api.fetchMarketDates(list), `?${listQuery}`],
		["get_market_date", (api) => api.fetchMarketDate(name), nameQuery],
		["get_exchange_rates", (api) => api.fetchExchangeRates(list), `?${listQuery}`],
		["get_exchange_rate", (api) => api.fetchExchangeRate(name), nameQuery],
		["get_portfolio_performance", (api) => api.fetchPortfolioPerformance(portfolio),
			`?${portfolioQuery}`],
		["get_interest_difference_by_portfolio", (api) => api.fetchInterestDifference({
			...dates, portfolio: "PF-1",
		}), `?portfolio=PF-1&${dateQuery}`],
		["get_portfolio_performance_cashflows", (api) => api.fetchPortfolioPerformanceCashflows({
			...portfolio, isin: "BOND-1", xirrType: "future", cashflowCurrency: "reporting",
		}), `?${portfolioQuery}&isin=BOND-1&xirr_type=future&cashflow_currency=reporting`],
		["get_bond_yield_comparison", (api) => api.fetchBondYieldComparison(dates), `?${dateQuery}`],
		["get_yield_comparison_defaults", (api) => api.fetchYieldComparisonDefaults(), ""],
		["get_transactions", (api) => api.fetchTransactions({}), ""],
		["get_statements", (api) => api.fetchStatements({}), ""],
		["get_bonds", (api) => api.fetchBonds({}), ""],
		["get_market_dates", (api) => api.fetchMarketDates({}), ""],
		["get_exchange_rates", (api) => api.fetchExchangeRates({}), ""],
		["get_interest_difference_by_portfolio", (api) => api.fetchInterestDifference({ portfolio: "PF-1" }),
			"?portfolio=PF-1"],
		["get_bond_yield_comparison", (api) => api.fetchBondYieldComparison({}), ""],
	];
	it.each(endpoints)("maps %s", async (method, call, query) => {
		const data = { name: "returned data" };
		const fetchMock = stubFetch(200, { data });
		await expect(call(useInvestorApi())).resolves.toEqual(data);
		expect(fetchMock).toHaveBeenCalledOnce();
		expect(fetchMock.mock.calls[0][0]).toBe(`${METHOD_URL}.${method}${query}`);
		expect(fetchMock.mock.calls[0][1]?.method ?? "GET").toBe("GET");
	});

	it("sends the frappe-ui request headers", async () => {
		stubBrowser("user_id=investor%40example.com", "token-1");
		const fetchMock = stubFetch(200, { data: {} });

		await useInvestorApi().fetchBootstrap();
		expect(fetchMock.mock.calls[0][1]).toEqual({
			headers: {
				Accept: "application/json",
				"X-Frappe-Site-Name": "bond-management-test.localhost",
				"X-Frappe-CSRF-Token": "token-1",
			},
		});
	});

	it("omits an unrendered CSRF token placeholder", async () => {
		stubBrowser("user_id=investor%40example.com", "{{ csrf_token }}");
		const fetchMock = stubFetch(200, { data: {} });

		await useInvestorApi().fetchBootstrap();
		expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty("X-Frappe-CSRF-Token");
	});

	it("maps HTTP 401 to 401 with or without status text", async () => {
		stubFetch(401, v1Error("AuthenticationError"), "UNAUTHORIZED");
		await expectStatus(401);
		stubFetch(401, {});
		await expectStatus(401);
	});

	it("maps HTTP 403 to 403 for a signed-in user, even over HTTP/2", async () => {
		stubFetch(403, v1Error("PermissionError"), "FORBIDDEN");
		await expectStatus(403);
		// HTTP/2 responses have no status text.
		stubFetch(403, v1Error("PermissionError"));
		await expectStatus(403);
	});

	it("maps HTTP 403 to 401 when the session is Guest", async () => {
		stubBrowser("user_id=Guest; sid=Guest");
		stubFetch(403, v1Error("PermissionError"));
		await expectStatus(401);
	});

	it("falls back to exc_type when the status is not 401 or 403", async () => {
		stubFetch(500, v1Error("AuthenticationError"));
		await expectStatus(401);
		stubFetch(500, v1Error("PermissionError"));
		await expectStatus(403);
	});

	it("maps any other error to 500", async () => {
		stubFetch(417, v1Error("ValidationError"), "EXPECTATION FAILED");
		await expectStatus(500);
		stubFetch(404, v1Error("DoesNotExistError"));
		await expectStatus(500);
	});

	it("maps a non-JSON error body to 500", async () => {
		stubFetch(502, "<html>Bad Gateway</html>");
		await expectStatus(500);
	});

	it("maps a network failure to 500", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn(async () => {
				throw new TypeError("Failed to fetch");
			})
		);
		await expectStatus(500);
	});

	it("maps a success without data to 500", async () => {
		stubFetch(200, { data: null });
		await expectStatus(500);
		stubFetch(200, { message: { name: "BOND-1" } });
		await expectStatus(500);
		stubFetch(200, "not json");
		await expectStatus(500);
	});

	it("never returns an earlier response when a later request fails", async () => {
		const api = useInvestorApi();
		stubFetch(200, { data: { name: "BOND-1" } });
		await expect(api.fetchBond("BOND-1")).resolves.toEqual({ name: "BOND-1" });

		vi.stubGlobal(
			"fetch",
			vi.fn(async () => {
				throw new TypeError("Failed to fetch");
			})
		);
		await expect(api.fetchBond("BOND-2")).rejects.toBeInstanceOf(InvestorApiError);
	});
});

describe("redirectToLogin", () => {
	it("sends the browser to login with the current route as the redirect target", () => {
		const assign = vi.fn();
		vi.stubGlobal("window", {
			location: { pathname: "/bond-investor/bonds", search: "?sort=asc", hash: "#top", assign },
		});

		redirectToLogin();

		expect(assign).toHaveBeenCalledOnce();
		expect(assign).toHaveBeenCalledWith(
			"/login?redirect-to=%2Fbond-investor%2Fbonds%3Fsort%3Dasc%23top"
		);
	});
});
