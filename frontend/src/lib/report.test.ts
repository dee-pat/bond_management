import { describe, expect, it, vi } from "vitest";

import { InvestorApiError, redirectToLogin } from "./api";
import { useReportRequest } from "./report";

vi.mock("./api", async (importOriginal) => ({
	...(await importOriginal<typeof import("./api")>()),
	redirectToLogin: vi.fn(),
}));

interface Report {
	rows: string[];
}

const ERROR_MESSAGE = "Report could not be loaded. Please retry.";

function deferred() {
	let resolve!: (response: { report: Report }) => void;
	let reject!: (error: unknown) => void;
	const promise = new Promise<{ report: Report }>((onResolve, onReject) => {
		resolve = onResolve;
		reject = onReject;
	});
	return { promise, resolve, reject };
}

function setup() {
	const requests: ReturnType<typeof deferred>[] = [];
	const fetcher = vi.fn(() => {
		const request = deferred();
		requests.push(request);
		return request.promise;
	});
	return { state: useReportRequest(fetcher, ERROR_MESSAGE), fetcher, requests };
}

describe("useReportRequest", () => {
	it("starts idle without fetching and exposes pending state during a run", async () => {
		const { state, fetcher, requests } = setup();
		expect(fetcher).not.toHaveBeenCalled();
		expect(state.report.value).toBeNull();
		expect(state.error.value).toBeNull();
		expect(state.loading.value).toBe(false);
		expect(state.hasRun.value).toBe(false);

		const pending = state.load();
		expect(fetcher).toHaveBeenCalledOnce();
		expect(state.loading.value).toBe(true);
		expect(state.hasRun.value).toBe(true);
		requests[0].resolve({ report: { rows: ["first"] } });
		await pending;
		expect(state.report.value).toEqual({ rows: ["first"] });
		expect(state.loading.value).toBe(false);
	});

	it("clears a previous result before rerunning and keeps empty reports successful", async () => {
		const { state, requests } = setup();
		const first = state.load();
		requests[0].resolve({ report: { rows: ["first"] } });
		await first;

		const second = state.load();
		expect(state.report.value).toBeNull();
		requests[1].resolve({ report: { rows: [] } });
		await second;
		expect(state.report.value).toEqual({ rows: [] });
		expect(state.error.value).toBeNull();
		expect(state.hasRun.value).toBe(true);
	});

	it.each([new InvestorApiError(403), new InvestorApiError(500), new Error("private server text")])(
		"shows the page's generic message after failure and recovers on retry (%s)",
		async (error) => {
			const { state, requests } = setup();
			const first = state.load();
			requests[0].resolve({ report: { rows: ["old"] } });
			await first;
			const failed = state.load();
			requests[1].reject(error);
			await failed;
			expect(state.report.value).toBeNull();
			expect(state.error.value).toBe(ERROR_MESSAGE);
			expect(state.loading.value).toBe(false);
			expect(state.hasRun.value).toBe(true);
			expect(redirectToLogin).not.toHaveBeenCalled();

			const retry = state.load();
			expect(state.error.value).toBeNull();
			expect(state.loading.value).toBe(true);
			requests[2].resolve({ report: { rows: ["recovered"] } });
			await retry;
			expect(state.report.value).toEqual({ rows: ["recovered"] });
		}
	);

	it("handles a synchronous fetcher failure", async () => {
		const state = useReportRequest<Report>(() => {
			throw new Error("offline");
		}, ERROR_MESSAGE);
		await state.load();
		expect(state.error.value).toBe(ERROR_MESSAGE);
		expect(state.loading.value).toBe(false);
	});

	it("redirects only a current authentication failure", async () => {
		const { state, requests } = setup();
		const pending = state.load();
		requests[0].reject(new InvestorApiError(401));
		await pending;
		expect(redirectToLogin).toHaveBeenCalledOnce();
		expect(state.report.value).toBeNull();
		expect(state.error.value).toBeNull();
		expect(state.loading.value).toBe(false);
	});

	it.each(["success", "failure", "authentication"])("keeps a newer request pending after stale %s", async (outcome) => {
		const { state, requests } = setup();
		const older = state.load();
		const newer = state.load();
		if (outcome === "success") {
			requests[0].resolve({ report: { rows: ["old"] } });
		} else {
			requests[0].reject(new InvestorApiError(outcome === "authentication" ? 401 : 500));
		}
		await older;
		expect(state.report.value).toBeNull();
		expect(state.error.value).toBeNull();
		expect(state.loading.value).toBe(true);
		expect(redirectToLogin).not.toHaveBeenCalled();
		requests[1].resolve({ report: { rows: ["new"] } });
		await newer;
		expect(state.report.value).toEqual({ rows: ["new"] });
	});

	it.each(["success", "failure", "authentication"])("ignores stale %s after a newer success", async (outcome) => {
		const { state, requests } = setup();
		const older = state.load();
		const newer = state.load();
		requests[1].resolve({ report: { rows: ["new"] } });
		await newer;
		if (outcome === "success") {
			requests[0].resolve({ report: { rows: ["old"] } });
		} else {
			requests[0].reject(new InvestorApiError(outcome === "authentication" ? 401 : 500));
		}
		await older;
		expect(state.report.value).toEqual({ rows: ["new"] });
		expect(state.error.value).toBeNull();
		expect(state.loading.value).toBe(false);
		expect(redirectToLogin).not.toHaveBeenCalled();
	});

	it.each(["success", "failure", "authentication"])("invalidates pending %s without repopulating the initial view", async (outcome) => {
		const { state, requests } = setup();
		const pending = state.load();
		state.invalidate();
		if (outcome === "success") {
			requests[0].resolve({ report: { rows: ["old"] } });
		} else {
			requests[0].reject(new InvestorApiError(outcome === "authentication" ? 401 : 500));
		}
		await pending;
		expect(state.report.value).toBeNull();
		expect(state.error.value).toBeNull();
		expect(state.loading.value).toBe(false);
		expect(state.hasRun.value).toBe(false);
		expect(redirectToLogin).not.toHaveBeenCalled();
	});

	it("does not share results or request tokens across report instances", async () => {
		const first = setup();
		const second = setup();
		const firstRun = first.state.load();
		const secondRun = second.state.load();
		first.state.invalidate();
		first.requests[0].resolve({ report: { rows: ["ignored"] } });
		second.requests[0].resolve({ report: { rows: ["second"] } });
		await Promise.all([firstRun, secondRun]);
		expect(first.state.report.value).toBeNull();
		expect(second.state.report.value).toEqual({ rows: ["second"] });
	});
});
