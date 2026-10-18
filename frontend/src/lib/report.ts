import { ref, shallowRef } from "vue";

import { InvestorApiError, redirectToLogin } from "./api";

export function useReportRequest<T>(
	fetcher: () => Promise<{ report: T }>,
	errorMessage: string
) {
	const report = shallowRef<T | null>(null);
	const loading = ref(false);
	const hasRun = ref(false);
	const error = ref<string | null>(null);
	let latestRequest = 0;

	async function load(): Promise<void> {
		const requestId = ++latestRequest;
		hasRun.value = true;
		loading.value = true;
		error.value = null;
		report.value = null;

		try {
			const response = await fetcher();
			if (requestId === latestRequest) {
				report.value = response.report;
			}
		} catch (caughtError) {
			if (requestId !== latestRequest) {
				return;
			}
			if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
				redirectToLogin();
				return;
			}
			error.value = errorMessage;
		} finally {
			if (requestId === latestRequest) {
				loading.value = false;
			}
		}
	}

	function invalidate(): void {
		++latestRequest;
		report.value = null;
		loading.value = false;
		hasRun.value = false;
		error.value = null;
	}

	return { report, loading, hasRun, error, load, invalidate };
}
