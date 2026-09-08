<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { Button } from "frappe-ui";
import { ListCell, ListHeaderCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import { formatDate, formatMoney, formatNumber, formatPercent } from "../lib/format";
import type { BondDetail } from "../types";

type BondScalarField = Exclude<keyof BondDetail, "principal_schedule" | "coupon_schedule">;

interface DetailField {
	fieldname: BondScalarField;
	label: string;
	format?: "boolean" | "date" | "money" | "percent";
}

const DETAIL_FIELDS: DetailField[] = [
	{ fieldname: "bond_name", label: "Bond Name" },
	{ fieldname: "isin", label: "ISIN" },
	{ fieldname: "issue_date", label: "Issue Date", format: "date" },
	{ fieldname: "first_coupon_date", label: "First Coupon Date", format: "date" },
	{ fieldname: "face_value_per_unit", label: "Face Value Per Unit", format: "money" },
	{ fieldname: "coupon_frequency", label: "Coupon Frequency" },
	{ fieldname: "bond_type", label: "Bond Type" },
	{ fieldname: "maturity_date", label: "Maturity Date", format: "date" },
	{ fieldname: "currency", label: "Currency" },
	{ fieldname: "coupon_rate", label: "Coupon Rate %", format: "percent" },
	{ fieldname: "withholding_tax", label: "Withholding Tax %", format: "percent" },
	{ fieldname: "day_count_convention", label: "Day Count Convention" },
	{ fieldname: "quantity_change", label: "Quantity Change", format: "boolean" },
];

const route = useRoute();
const bond = ref<BondDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const bondName = computed(() => String(route.params.bondName ?? ""));
const api = useInvestorApi();
let latestRequest = 0;

async function loadBond(): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await api.fetchBond(bondName.value);
		if (requestId === latestRequest) {
			bond.value = response.bond;
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
				? "This bond is unavailable or you do not have permission to view it."
				: "The bond could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

function displayValue(field: DetailField): string {
	if (!bond.value) {
		return "—";
	}

	const value = bond.value[field.fieldname];
	if (field.format === "date") {
		return formatDate(String(value));
	}
	if (field.format === "money") {
		return formatMoney(Number(value), bond.value.currency);
	}
	if (field.format === "percent") {
		return formatPercent(Number(value));
	}
	if (field.format === "boolean") {
		return value ? "Yes" : "No";
	}
	return String(value || "—");
}

onMounted(() => void loadBond());
</script>

<template>
	<section class="record-surface" aria-labelledby="bond-detail-title">
		<RouterLink class="back-link" to="/bonds"> ← Back to bonds </RouterLink>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading bond…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<Button label="Retry" variant="outline" @click="loadBond" />
		</div>

		<template v-else-if="bond">
			<div class="surface-heading">
				<div>
					<p class="surface-kicker">ISIN</p>
					<h2 id="bond-detail-title">
						{{ bond.isin }}
					</h2>
				</div>
				<span class="read-only-badge">Read only</span>
			</div>

			<dl class="record-detail-grid" data-testid="bond-detail">
				<div v-for="field in DETAIL_FIELDS" :key="field.fieldname">
					<dt>{{ field.label }}</dt>
					<dd>{{ displayValue(field) }}</dd>
				</div>
			</dl>

			<section class="schedule-section">
				<h3>Principal Schedule</h3>
				<div v-if="bond.principal_schedule.length === 0" class="surface-state">
					This bond has no principal schedule.
				</div>
				<div v-else>
					<DataList
						:items="bond.principal_schedule"
						:columns="['minmax(12rem,1fr)', 'minmax(12rem,1fr)', 'minmax(10rem,1fr)']"
						row-key="repayment_date"
						data-testid="principal-schedule"
					>
						<template #header>
							<ListHeaderCell>Repayment Date</ListHeaderCell>
							<ListHeaderCell>Principal Units</ListHeaderCell>
							<ListHeaderCell>Repayment %</ListHeaderCell>
						</template>
						<template #row="{ item: row }">
							<ListCell data-label="Repayment Date">
								{{ formatDate(row.repayment_date) }}
							</ListCell>
							<ListCell data-label="Principal Units">
								{{ formatNumber(row.principal_units) }}
							</ListCell>
							<ListCell data-label="Repayment %">
								{{ formatPercent(row.repayment_percent) }}
							</ListCell>
						</template>
					</DataList>
				</div>
			</section>

			<section class="schedule-section">
				<h3>Coupon Schedule</h3>
				<div v-if="bond.coupon_schedule.length === 0" class="surface-state">
					This bond has no coupon schedule.
				</div>
				<div v-else>
					<DataList
						:items="bond.coupon_schedule"
						:columns="[
							'minmax(10rem,1fr)',
							'minmax(10rem,1fr)',
							'minmax(10rem,1fr)',
							'minmax(10rem,1fr)',
						]"
						row-key="coupon_date"
						data-testid="coupon-schedule"
					>
						<template #header>
							<ListHeaderCell>Coupon Date</ListHeaderCell>
							<ListHeaderCell>Period Start</ListHeaderCell>
							<ListHeaderCell>Period End</ListHeaderCell>
							<ListHeaderCell>Coupon Factor</ListHeaderCell>
						</template>
						<template #row="{ item: row }">
							<ListCell data-label="Coupon Date">
								{{ formatDate(row.coupon_date) }}
							</ListCell>
							<ListCell data-label="Period Start">
								{{ formatDate(row.period_start) }}
							</ListCell>
							<ListCell data-label="Period End">
								{{ formatDate(row.period_end) }}
							</ListCell>
							<ListCell data-label="Coupon Factor">
								{{ formatPercent(row.coupon_factor) }}
							</ListCell>
						</template>
					</DataList>
				</div>
			</section>
		</template>
	</section>
</template>
