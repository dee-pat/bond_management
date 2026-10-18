import { describe, expect, it, vi } from "vitest";

import { InvestorApiError, redirectToLogin } from "./api";
import { useReportRequest } from "./report";

vi.mock("./api", async (importOriginal) => ({
	...(await importOriginal<typeof import("./api")>()),
	redirectToLogin: vi.fn()
}));

interface Report {
	rows: string[];
}
const ERROR_MESSAGE = "Report could not be loaded. Please retry.";
const IDLE = { report: null, error: null, loading: false, hasRun: false };
const PENDING = { ...IDLE, loading: true, hasRun: true };
const FINISHED = { ...PENDING, loading: false };

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
	const state = useReportRequest(fetcher, ERROR_MESSAGE);
	const snapshot = () => ({
		report: state.report.value,
		error: state.error.value,
		loading: state.loading.value,
		hasRun: state.hasRun.value
	});
	return { state, fetcher, requests, snapshot };
}

describe("useReportRequest", () => {
	it("starts idle, exposes pending state and displays a successful report", async () => {
		const { state, fetcher, requests, snapshot } = setup();
		expect(fetcher).not.toHaveBeenCalled();
		expect(snapshot()).toEqual(IDLE);
		const pending = state.load();
		expect(fetcher).toHaveBeenCalledOnce();
		expect(snapshot()).toEqual(PENDING);
		requests[0].resolve({ report: { rows: ["first"] } });
		await pending;
		expect(snapshot()).toEqual({ ...FINISHED, report: { rows: ["first"] } });
	});

	it("clears previous results before rerunning and accepts an empty report", async () => {
		const { state, requests, snapshot } = setup();
		const first = state.load();
		requests[0].resolve({ report: { rows: ["first"] } });
		await first;
		const second = state.load();
		expect(snapshot()).toEqual(PENDING);
		requests[1].resolve({ report: { rows: [] } });
		await second;
		expect(snapshot()).toEqual({ ...FINISHED, report: { rows: [] } });
	});

	it.each([new InvestorApiError(403), new InvestorApiError(500), new Error("private server text")])(
		"clears old data, shows the generic error and recovers on retry (%s)",
		async (error) => {
			const { state, requests, snapshot } = setup();
			const first = state.load();
			requests[0].resolve({ report: { rows: ["old"] } });
			await first;
			const failed = state.load();
			requests[1].reject(error);
			await failed;
			expect(snapshot()).toEqual({ ...FINISHED, error: ERROR_MESSAGE });
			expect(redirectToLogin).not.toHaveBeenCalled();
			const retry = state.load();
			expect(snapshot()).toEqual(PENDING);
			requests[2].resolve({ report: { rows: ["recovered"] } });
			await retry;
			expect(snapshot()).toEqual({
				...FINISHED,
				report: { rows: ["recovered"] }
			});
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

	it("redirects a current authentication failure", async () => {
		const { state, requests, snapshot } = setup();
		const pending = state.load();
		requests[0].reject(new InvestorApiError(401));
		await pending;
		expect(redirectToLogin).toHaveBeenCalledOnce();
		expect(snapshot()).toEqual(FINISHED);
	});

	const staleCases = ["success", "failure", "authentication"].flatMap((outcome) =>
		(["pending", "completed", "invalidated"] as const).map((phase) => ({ outcome, phase }))
	);
	it.each(staleCases)("ignores stale $outcome while $phase", async ({ outcome, phase }) => {
		const { state, requests, snapshot } = setup();
		const older = state.load();
		const newer = phase === "invalidated" ? undefined : state.load();
		if (phase === "invalidated") state.invalidate();
		if (phase === "completed") {
			requests[1].resolve({ report: { rows: ["new"] } });
			await newer;
		}
		if (outcome === "success") {
			requests[0].resolve({ report: { rows: ["old"] } });
		} else {
			requests[0].reject(new InvestorApiError(outcome === "authentication" ? 401 : 500));
		}
		await older;
		const completed = { ...FINISHED, report: { rows: ["new"] } };
		const expected = { pending: PENDING, completed, invalidated: IDLE };
		expect(snapshot()).toEqual(expected[phase]);
		expect(redirectToLogin).not.toHaveBeenCalled();
		if (phase === "pending") {
			requests[1].resolve({ report: { rows: ["new"] } });
			await newer;
			expect(snapshot()).toEqual(completed);
		}
	});

	it("keeps results and request tokens independent between instances", async () => {
		const first = setup();
		const second = setup();
		const firstRun = first.state.load();
		const secondRun = second.state.load();
		first.state.invalidate();
		first.requests[0].resolve({ report: { rows: ["ignored"] } });
		second.requests[0].resolve({ report: { rows: ["second"] } });
		await Promise.all([firstRun, secondRun]);
		expect(first.snapshot()).toEqual(IDLE);
		expect(second.snapshot()).toEqual({
			...FINISHED,
			report: { rows: ["second"] }
		});
	});
});
