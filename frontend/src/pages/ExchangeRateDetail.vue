<script setup lang="ts">
import { Badge } from "frappe-ui";
import { RouterLink, useRoute } from "vue-router";

import SurfaceState from "../components/SurfaceState.vue";
import { useInvestorApi } from "../lib/api";
import { useRecordDetail } from "../lib/detail";
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
const api = useInvestorApi();
const {
	record: exchangeRate,
	loading,
	error,
	load: loadExchangeRate,
} = useRecordDetail(
	async () =>
		(await api.fetchExchangeRate(String(route.params.exchangeRateName ?? ""))).exchange_rate,
	{
		forbidden: "This exchange rate is unavailable or you do not have permission to view it.",
		failed: "The exchange rate could not be loaded. Please retry.",
	}
);

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
</script>

<template>
	<section class="record-surface" aria-labelledby="exchange-rate-detail-title">
		<RouterLink class="back-link" to="/exchange-rates"> ← Back to exchange rates </RouterLink>

		<SurfaceState v-if="loading" :loading="loading" loading-text="Loading exchange rate…" />

		<SurfaceState v-else-if="error" :error="error" @retry="loadExchangeRate" />

		<template v-else-if="exchangeRate">
			<div class="surface-heading">
				<div>
					<p class="surface-kicker">From currency</p>
					<h2 id="exchange-rate-detail-title">
						{{ exchangeRate.from_currency }}
					</h2>
				</div>
				<Badge theme="gray" variant="outline" size="sm">Read only</Badge>
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
