<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { fetchExchangeRate, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate, formatNumber } from "../lib/format";
import type { ExchangeRateDetail } from "../types";

interface DetailField {
	fieldname: keyof ExchangeRateDetail;
	label: string;
	format?: "date" | "rate";
}

const DETAIL_FIELDS: DetailField[] = [
	{ fieldname: "rate_date", label: "Rate Date", format: "date" },
	{ fieldname: "from_currency", label: "From Currency" },
	{ fieldname: "to_currency", label: "To Currency" },
	{ fieldname: "source", label: "Source" },
	{ fieldname: "rate", label: "Rate", format: "rate" },
	{ fieldname: "reverse_rate", label: "Reverse Rate", format: "rate" },
	{ fieldname: "statement", label: "Statement" },
];

const route = useRoute();
const exchangeRate = ref<ExchangeRateDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const exchangeRateName = computed(() => String(route.params.exchangeRateName ?? ""));
let latestRequest = 0;

async function loadExchangeRate(): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchExchangeRate(exchangeRateName.value);
		if (requestId === latestRequest) {
			exchangeRate.value = response.exchange_rate;
		}
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value =
			caughtError instanceof InvestorApiError && caughtError.status === 403
				? "This exchange rate is unavailable or you do not have permission to view it."
				: "The exchange rate could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

function displayValue(field: DetailField): string {
	if (!exchangeRate.value) {
		return "—";
	}

	const value = exchangeRate.value[field.fieldname];
	if (value === null || value === "") {
		return "—";
	}
	if (field.format === "date") {
		return formatDate(String(value));
	}
	if (field.format === "rate") {
		return formatNumber(Number(value), 12);
	}
	return String(value);
}

onMounted(() => void loadExchangeRate());
</script>

<template>
	<section class="record-surface" aria-labelledby="exchange-rate-detail-title">
		<RouterLink class="back-link" to="/exchange-rates"> ← Back to exchange rates </RouterLink>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading exchange rate…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button class="secondary-button" type="button" @click="loadExchangeRate">Retry</button>
		</div>

		<template v-else-if="exchangeRate">
			<div class="surface-heading">
				<div>
					<p class="surface-kicker">From currency</p>
					<h2 id="exchange-rate-detail-title">
						{{ exchangeRate.from_currency }}
					</h2>
				</div>
				<span class="read-only-badge">Read only</span>
			</div>

			<dl class="record-detail-grid" data-testid="exchange-rate-detail">
				<div v-for="field in DETAIL_FIELDS" :key="field.fieldname">
					<dt>{{ field.label }}</dt>
					<dd>{{ displayValue(field) }}</dd>
				</div>
			</dl>
		</template>
	</section>
</template>
