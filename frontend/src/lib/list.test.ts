// @vitest-environment happy-dom
import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InvestorApiError, redirectToLogin } from "./api";
import { toFilterValue, usePagedList } from "./list";

vi.mock("./api", async (importOriginal) => ({
	...(await importOriginal<typeof import("./api")>()),
	redirectToLogin: vi.fn(),
}));

interface Row {
	name: string;
}

interface Page {
	data: Row[];
	pagination: { start: number; page_length: number; has_more: boolean };
}

interface Deferred {
	resolve: (page: Page) => void;
	reject: (error: unknown) => void;
}

const unmountAll: Array<() => void> = [];

afterEach(() => {
	unmountAll.splice(0).forEach((unmount) => unmount());
});

// Vue's testing guide: run a composable that uses lifecycle hooks inside a host app.
function withSetup<T>(composable: () => T): T {
	let result!: T;
	const app = createApp({
		setup() {
			result = composable();
			return () => null;
		},
	});
	app.mount(document.createElement("div"));
	unmountAll.push(() => app.unmount());
	return result;
}

function page(names: string[], hasMore = false, start = 0): Page {
	return {
		data: names.map((name) => ({ name })),
		pagination: { start, page_length: 20, has_more: hasMore },
	};
}

function mountList() {
	const pending: Deferred[] = [];
	const fetchPage = vi.fn(
		() =>
			new Promise<Page>((resolve, reject) => {
				pending.push({ resolve, reject });
			})
	);
	const list = withSetup(() =>
		usePagedList<Row>({ fetchPage, sortBy: "trade_date", errorMessage: "Could not load rows." })
	);
	return { list, fetchPage, pending };
}

async function settle(): Promise<void> {
	await new Promise((resolve) => setTimeout(resolve, 0));
	await nextTick();
}

describe("toFilterValue", () => {
	it("keeps strings and stringifies numbers", () => {
		expect(toFilterValue("USD")).toBe("USD");
		expect(toFilterValue(" ")).toBe(" ");
		expect(toFilterValue(42)).toBe("42");
		expect(toFilterValue(0)).toBe("0");
		expect(toFilterValue(false)).toBe("false");
	});

	it("returns null for null, undefined and the empty string", () => {
		expect(toFilterValue(null)).toBeNull();
		expect(toFilterValue(undefined)).toBeNull();
		expect(toFilterValue("")).toBeNull();
	});

	it("joins arrays with commas", () => {
		expect(toFilterValue(["a", "b"])).toBe("a,b");
		expect(toFilterValue([])).toBe("");
	});

	it("returns null for plain objects", () => {
		expect(toFilterValue({ name: "PF-1" })).toBeNull();
		expect(toFilterValue({})).toBeNull();
	});
});

describe("usePagedList", () => {
	it("loads the first page on mount", () => {
		const { list, fetchPage } = mountList();

		expect(list.loading.value).toBe(true);
		expect(list.error.value).toBeNull();
		expect(list.rows.value).toEqual([]);
		expect(fetchPage).toHaveBeenCalledWith({
			start: 0,
			pageLength: 20,
			sortBy: "trade_date",
			sortOrder: "desc",
			filterField: undefined,
			filterValue: undefined,
		});
	});

	it("shows the rows and pagination from a successful response", async () => {
		const { list, pending } = mountList();

		pending[0].resolve(page(["A", "B"], true));
		await settle();

		expect(list.loading.value).toBe(false);
		expect(list.error.value).toBeNull();
		expect(list.rows.value).toEqual([{ name: "A" }, { name: "B" }]);
		expect(list.pagination.value).toEqual({ start: 0, page_length: 20, has_more: true });
	});

	it("shows an empty list from an empty response", async () => {
		const { list, pending } = mountList();

		pending[0].resolve(page([]));
		await settle();

		expect(list.loading.value).toBe(false);
		expect(list.error.value).toBeNull();
		expect(list.rows.value).toEqual([]);
	});

	it("shows the configured message when the request fails", async () => {
		const { list, pending } = mountList();

		pending[0].reject(new InvestorApiError(403));
		await settle();

		expect(list.loading.value).toBe(false);
		expect(list.error.value).toBe("Could not load rows.");
		expect(list.rows.value).toEqual([]);
		expect(redirectToLogin).not.toHaveBeenCalled();
	});

	it("clears the error and rows when retrying", async () => {
		const { list, pending } = mountList();
		pending[0].reject(new Error("offline"));
		await settle();

		list.retry();

		expect(list.loading.value).toBe(true);
		expect(list.error.value).toBeNull();
		pending[1].resolve(page(["A"]));
		await settle();
		expect(list.rows.value).toEqual([{ name: "A" }]);
	});

	it("redirects to login on an authentication error", async () => {
		const { list, pending } = mountList();

		pending[0].reject(new InvestorApiError(401));
		await settle();

		expect(redirectToLogin).toHaveBeenCalledOnce();
		expect(list.error.value).toBeNull();
		expect(list.loading.value).toBe(false);
	});

	it("keeps the newer response when an older one resolves last", async () => {
		const { list, fetchPage, pending } = mountList();

		list.changeSort("settlement_date", "asc");
		expect(fetchPage).toHaveBeenLastCalledWith(
			expect.objectContaining({ sortBy: "settlement_date", sortOrder: "asc" })
		);
		pending[1].resolve(page(["newer"]));
		await settle();
		pending[0].resolve(page(["older"], true));
		await settle();

		expect(list.rows.value).toEqual([{ name: "newer" }]);
		expect(list.pagination.value.has_more).toBe(false);
		expect(list.loading.value).toBe(false);
	});

	it("stays loading when an older response resolves before the newer one", async () => {
		const { list, pending } = mountList();

		list.applyFilter("currency", "Currency", "USD");
		pending[0].resolve(page(["older"]));
		await settle();

		expect(list.loading.value).toBe(true);
		expect(list.rows.value).toEqual([]);
	});

	it("ignores a stale failure and a stale authentication error", async () => {
		const { list, pending } = mountList();

		list.clearFilter();
		list.changePageLength(50);
		pending[2].resolve(page(["newest"]));
		await settle();
		pending[0].reject(new InvestorApiError(401));
		pending[1].reject(new Error("offline"));
		await settle();

		expect(list.rows.value).toEqual([{ name: "newest" }]);
		expect(list.error.value).toBeNull();
		expect(redirectToLogin).not.toHaveBeenCalled();
	});

	it("appends the next page and skips loadMore while loading or at the end", async () => {
		const { list, fetchPage, pending } = mountList();

		list.loadMore();
		expect(fetchPage).toHaveBeenCalledTimes(1);

		pending[0].resolve(page(["A"], true));
		await settle();
		list.loadMore();
		expect(fetchPage).toHaveBeenLastCalledWith(expect.objectContaining({ start: 20 }));
		pending[1].resolve(page(["B"], false, 20));
		await settle();

		expect(list.rows.value).toEqual([{ name: "A" }, { name: "B" }]);
		list.loadMore();
		expect(fetchPage).toHaveBeenCalledTimes(2);
	});

	it("applies a filter value but ignores an empty or object one", () => {
		const { list, fetchPage } = mountList();

		list.applyFilter("currency", "Currency", "");
		list.applyFilter("portfolio", "Portfolio", { name: "PF-1" });
		expect(fetchPage).toHaveBeenCalledTimes(1);
		expect(list.activeFilter.value).toBeNull();

		list.applyFilter("quantity", "Quantity", 100);
		expect(list.activeFilter.value).toEqual({ field: "quantity", label: "Quantity", value: "100" });
		expect(fetchPage).toHaveBeenLastCalledWith(
			expect.objectContaining({ start: 0, filterField: "quantity", filterValue: "100" })
		);
	});
});
