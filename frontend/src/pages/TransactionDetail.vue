<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import PdfAttachmentActions from "../components/PdfAttachmentActions.vue";
import { fetchTransaction, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate, formatMoney, formatNumber, formatPercent } from "../lib/format";
import type { TransactionDetail } from "../types";

interface DetailField {
	fieldname: keyof TransactionDetail;
	label: string;
	format?: "date" | "money" | "percent" | "price" | "quantity";
}

const DETAIL_FIELDS: DetailField[] = [
	{ fieldname: "transaction_type", label: "Transaction Type" },
	{ fieldname: "portfolio_name", label: "Portfolio Name" },
	{ fieldname: "isin", label: "ISIN" },
	{ fieldname: "bond_name", label: "Bond Name" },
	{ fieldname: "account_number", label: "Account Number" },
	{ fieldname: "transaction_reference", label: "Transaction Reference" },
	{ fieldname: "trade_date", label: "Trade Date", format: "date" },
	{ fieldname: "settlement_date", label: "Settlement Date", format: "date" },
	{ fieldname: "quantity_face_value", label: "Quantity/ Face Value", format: "quantity" },
	{ fieldname: "price", label: "Price", format: "price" },
	{ fieldname: "principal", label: "Principal", format: "money" },
	{ fieldname: "commission", label: "Commission %", format: "percent" },
	{
		fieldname: "accrued_interest_calculated",
		label: "Accrued Interest Calculated",
		format: "money",
	},
	{ fieldname: "accrued_interest_paid", label: "Accrued Interest Paid", format: "money" },
	{ fieldname: "currency", label: "Currency" },
	{ fieldname: "maturity_date", label: "Maturity Date", format: "date" },
	{ fieldname: "coupon_frequency", label: "Coupon frequency" },
	{ fieldname: "coupon_rate", label: "Coupon Rate %", format: "percent" },
	{ fieldname: "face_value_per_unit", label: "Face Value Per Unit", format: "money" },
	{ fieldname: "issue_date", label: "Issue Date", format: "date" },
	{ fieldname: "day_count_convention", label: "Day Count Convention" },
	{ fieldname: "commission_amount", label: "Commission Amount", format: "money" },
	{ fieldname: "settlement_amount", label: "Settlement Amount", format: "money" },
	{ fieldname: "transaction_amount", label: "Transaction Amount", format: "money" },
];

const route = useRoute();
const transaction = ref<TransactionDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const transactionName = computed(() => String(route.params.transactionName ?? ""));
let latestRequest = 0;

async function loadTransaction(): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchTransaction(transactionName.value);
		if (requestId === latestRequest) {
			transaction.value = response.transaction;
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
				? "This transaction is unavailable or you do not have permission to view it."
				: "The transaction could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

function displayValue(field: DetailField): string {
	if (!transaction.value) {
		return "—";
	}

	const value = transaction.value[field.fieldname];
	if (field.format === "date") {
		return formatDate(String(value));
	}
	if (field.format === "money") {
		return formatMoney(Number(value), transaction.value.currency);
	}
	if (field.format === "percent") {
		return formatPercent(Number(value));
	}
	if (field.format === "price") {
		return formatNumber(Number(value), 6);
	}
	if (field.format === "quantity") {
		return formatNumber(Number(value));
	}
	return String(value || "—");
}

onMounted(() => void loadTransaction());
</script>

<template>
	<section class="transaction-surface" aria-labelledby="transaction-detail-title">
		<RouterLink class="back-link" to="/transactions"> ← Back to transactions </RouterLink>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading transaction…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button class="secondary-button" type="button" @click="loadTransaction">Retry</button>
		</div>

		<template v-else-if="transaction">
			<div class="surface-heading">
				<div>
					<p class="surface-kicker">Transaction reference</p>
					<h2 id="transaction-detail-title">
						{{ transaction.transaction_reference }}
					</h2>
				</div>
				<span class="read-only-badge">Read only</span>
			</div>

			<dl class="transaction-detail-grid" data-testid="transaction-detail">
				<div v-for="field in DETAIL_FIELDS" :key="field.fieldname">
					<dt>{{ field.label }}</dt>
					<dd>{{ displayValue(field) }}</dd>
				</div>
			</dl>

			<section class="pdf-attachment-section" aria-labelledby="transaction-pdf-title">
				<h3 id="transaction-pdf-title">PDF Attachment</h3>
				<PdfAttachmentActions
					:attachment="transaction.attachment"
					:document-label="`transaction ${transaction.transaction_reference}`"
					file-label="PDF"
				/>
			</section>
		</template>
	</section>
</template>
