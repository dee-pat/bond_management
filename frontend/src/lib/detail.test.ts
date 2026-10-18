// @vitest-environment happy-dom
import { describe, expect, it, vi } from "vitest";

import { settle, withSetup } from "../test-utils/composable";
import { InvestorApiError, redirectToLogin } from "./api";
import { useRecordDetail } from "./detail";

vi.mock("./api", async (importOriginal) => ({
	...(await importOriginal<typeof import("./api")>()),
	redirectToLogin: vi.fn(),
}));

interface Bond {
	name: string;
}

interface Deferred {
	resolve: (record: Bond) => void;
	reject: (error: unknown) => void;
}

const MESSAGES = { forbidden: "You cannot view this bond.", failed: "Could not load the bond." };

function mountDetail() {
	const pending: Deferred[] = [];
	const fetcher = vi.fn(
		() =>
			new Promise<Bond>((resolve, reject) => {
				pending.push({ resolve, reject });
			})
	);
	const detail = withSetup(() => useRecordDetail<Bond>(fetcher, MESSAGES));
	return { detail, fetcher, pending };
}

describe("useRecordDetail", () => {
	it("loads the record on mount", () => {
		const { detail, fetcher } = mountDetail();

		expect(fetcher).toHaveBeenCalledOnce();
		expect(detail.loading.value).toBe(true);
		expect(detail.error.value).toBeNull();
		expect(detail.record.value).toBeNull();
	});

	it("shows the record from a successful response", async () => {
		const { detail, pending } = mountDetail();

		pending[0].resolve({ name: "BOND-1" });
		await settle();

		expect(detail.loading.value).toBe(false);
		expect(detail.error.value).toBeNull();
		expect(detail.record.value).toEqual({ name: "BOND-1" });
	});

	it("shows the forbidden message for a 403", async () => {
		const { detail, pending } = mountDetail();

		pending[0].reject(new InvestorApiError(403));
		await settle();

		expect(detail.loading.value).toBe(false);
		expect(detail.error.value).toBe(MESSAGES.forbidden);
		expect(detail.record.value).toBeNull();
	});

	it("shows the failed message for any other error", async () => {
		const { detail, pending } = mountDetail();

		pending[0].reject(new InvestorApiError(500));
		await settle();
		expect(detail.error.value).toBe(MESSAGES.failed);

		void detail.load();
		pending[1].reject(new Error("offline"));
		await settle();
		expect(detail.error.value).toBe(MESSAGES.failed);
		expect(redirectToLogin).not.toHaveBeenCalled();
	});

	it("clears the error while reloading", async () => {
		const { detail, pending } = mountDetail();
		pending[0].reject(new InvestorApiError(500));
		await settle();

		void detail.load();

		expect(detail.loading.value).toBe(true);
		expect(detail.error.value).toBeNull();
		pending[1].resolve({ name: "BOND-1" });
		await settle();
		expect(detail.record.value).toEqual({ name: "BOND-1" });
	});

	it("redirects to login on an authentication error", async () => {
		const { detail, pending } = mountDetail();

		pending[0].reject(new InvestorApiError(401));
		await settle();

		expect(redirectToLogin).toHaveBeenCalledOnce();
		expect(detail.error.value).toBeNull();
		expect(detail.loading.value).toBe(false);
	});

	it("keeps the newer record when an older response resolves last", async () => {
		const { detail, pending } = mountDetail();

		void detail.load();
		pending[1].resolve({ name: "newer" });
		await settle();
		pending[0].resolve({ name: "older" });
		await settle();

		expect(detail.record.value).toEqual({ name: "newer" });
		expect(detail.loading.value).toBe(false);
	});

	it("stays loading when an older response resolves before the newer one", async () => {
		const { detail, pending } = mountDetail();

		void detail.load();
		pending[0].resolve({ name: "older" });
		await settle();

		expect(detail.loading.value).toBe(true);
		expect(detail.record.value).toBeNull();
	});

	it("ignores a stale failure and a stale authentication error", async () => {
		const { detail, pending } = mountDetail();

		void detail.load();
		void detail.load();
		pending[2].resolve({ name: "newest" });
		await settle();
		pending[0].reject(new InvestorApiError(401));
		pending[1].reject(new InvestorApiError(403));
		await settle();

		expect(detail.record.value).toEqual({ name: "newest" });
		expect(detail.error.value).toBeNull();
		expect(redirectToLogin).not.toHaveBeenCalled();
	});
});
