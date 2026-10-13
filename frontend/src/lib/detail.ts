import { onMounted, shallowRef, ref } from "vue";

import { InvestorApiError, redirectToLogin } from "./api";

interface DetailMessages {
	forbidden: string;
	failed: string;
}

export function useRecordDetail<T>(
	fetcher: () => Promise<T>,
	messages: DetailMessages
) {
	const record = shallowRef<T | null>(null);
	const loading = ref(true);
	const error = ref<string | null>(null);
	let latestRequest = 0;

	async function load(): Promise<void> {
		const requestId = ++latestRequest;
		loading.value = true;
		error.value = null;

		try {
			const response = await fetcher();
			if (requestId === latestRequest) {
				record.value = response;
			}
		} catch (caughtError) {
			if (requestId !== latestRequest) {
				return;
			}
			if (
				caughtError instanceof InvestorApiError &&
				caughtError.status === 401
			) {
				redirectToLogin();
				return;
			}
			error.value =
				caughtError instanceof InvestorApiError && caughtError.status === 403
					? messages.forbidden
					: messages.failed;
		} finally {
			if (requestId === latestRequest) {
				loading.value = false;
			}
		}
	}

	onMounted(() => void load());

	return { record, loading, error, load };
}
