import { describe, expect, it, vi } from "vitest";

import { InvestorApiError, redirectToLogin, useInvestorApi } from "./api";

// The "frappe-ui" barrel imports .vue components. Load only the real useCall
// so requests run through frappe-ui's own fetch and error parsing.
vi.mock("frappe-ui", () => import("../../node_modules/frappe-ui/src/data-fetching/useCall/useCall"));

const METHOD_URL = "/api/method/bond_management.bond_management.api.investor";

function stubFetch(status: number, body: unknown) {
	const fetchMock = vi.fn(
		async (_input: RequestInfo | URL, _init?: RequestInit) =>
			new Response(typeof body === "string" ? body : JSON.stringify(body), {
				status,
				headers: { "Content-Type": "application/json" },
			})
	);
	vi.stubGlobal("fetch", fetchMock);
	return fetchMock;
}

function frappeError(type: string, message = "") {
	return { errors: [{ type, message, title: type, indicator: "red" }] };
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
	it("returns the response data from a GET to the investor method", async () => {
		const fetchMock = stubFetch(200, { data: { name: "BOND-1" } });

		await expect(useInvestorApi().fetchBond("BOND-1")).resolves.toEqual({ name: "BOND-1" });
		expect(fetchMock).toHaveBeenCalledOnce();
		expect(fetchMock.mock.calls[0][0]).toBe(`${METHOD_URL}.get_bond?name=BOND-1`);
	});

	it("sends list options as snake_case parameters and omits unset ones", async () => {
		const fetchMock = stubFetch(200, { data: { data: [], pagination: {} } });

		await useInvestorApi().fetchTransactions({
			portfolio: "PF-1",
			start: 20,
			pageLength: 20,
			sortBy: "trade_date",
			sortOrder: "asc",
		});
		expect(fetchMock.mock.calls[0][0]).toBe(
			`${METHOD_URL}.get_transactions?portfolio=PF-1&start=20&page_length=20&sort_by=trade_date&sort_order=asc`
		);
	});

	it("maps a Frappe AuthenticationError to 401", async () => {
		stubFetch(401, frappeError("AuthenticationError"));
		await expectStatus(401);
	});

	it("maps a Frappe PermissionError to 403 for a signed-in user", async () => {
		vi.stubGlobal("document", { cookie: "user_id=investor%40example.com; sid=abc" });
		stubFetch(403, frappeError("PermissionError", "Not permitted"));
		await expectStatus(403);
	});

	it("maps a PermissionError to 401 when the session is Guest", async () => {
		vi.stubGlobal("document", { cookie: "user_id=Guest; sid=Guest" });
		stubFetch(403, frappeError("PermissionError"));
		await expectStatus(401);
	});

	it("maps a forbidden message to 403", async () => {
		stubFetch(403, frappeError("HTTPError", "Forbidden"));
		await expectStatus(403);
	});

	it("maps any other Frappe error to 500", async () => {
		stubFetch(417, frappeError("ValidationError", "Invalid filter"));
		await expectStatus(500);
	});

	it("ignores the HTTP status when the body has no Frappe errors", async () => {
		// TODO(review): only the error type and message are consulted, so a 401 or
		// 403 without an `errors` payload maps to 500 and never redirects.
		stubFetch(403, { exc_type: "PermissionError" });
		await expectStatus(500);
		stubFetch(401, {});
		await expectStatus(500);
	});

	it("maps a non-JSON error body to 500", async () => {
		vi.spyOn(console, "log").mockImplementation(() => undefined);
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

	it("maps an empty success payload to 500", async () => {
		stubFetch(200, { data: null });
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
