<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import PdfAttachmentActions from "../components/PdfAttachmentActions.vue";
import { fetchTransactions, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate, formatNumber } from "../lib/format";
import type { InvestorBootstrap, TransactionListRow, TransactionPage } from "../types";

const props = defineProps<{ bootstrap: InvestorBootstrap }>();
const selectedPortfolio = ref("");
const transactions = ref<TransactionListRow[]>([]);
const pagination = ref<TransactionPage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
let latestRequest = 0;

const hasAssignments = computed(() => props.bootstrap.portfolios.length > 0);

async function loadTransactions(start = 0): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchTransactions({
			portfolio: selectedPortfolio.value || undefined,
			start,
			pageLength: pagination.value.page_length,
		});
		if (requestId !== latestRequest) {
			return;
		}
		transactions.value = response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Transactions could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

function changePortfolio(): void {
	void loadTransactions(0);
}

onMounted(() => void loadTransactions());
</script>

<template>
	<section class="transaction-surface" aria-labelledby="transaction-list-title">
		<div class="surface-heading">
			<div>
				<p class="surface-kicker">Assigned records</p>
				<h2 id="transaction-list-title">Transaction history</h2>
			</div>

			<label class="portfolio-filter">
				<span>Portfolio Name</span>
				<select
					v-model="selectedPortfolio"
					:disabled="loading || !hasAssignments"
					@change="changePortfolio"
				>
					<option value="">All assigned portfolios</option>
					<option
						v-for="portfolio in bootstrap.portfolios"
						:key="portfolio.name"
						:value="portfolio.name"
					>
						{{ portfolio.label }}
					</option>
				</select>
			</label>
		</div>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading transactions…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<button
				class="secondary-button"
				type="button"
				@click="loadTransactions(pagination.start)"
			>
				Retry
			</button>
		</div>

		<div v-else-if="!hasAssignments" class="surface-state" data-testid="transactions-empty">
			No portfolios are assigned to your account.
		</div>

		<div
			v-else-if="transactions.length === 0"
			class="surface-state"
			data-testid="transactions-empty"
		>
			No transactions match the selected portfolio.
		</div>

		<template v-else>
			<div class="transaction-table-wrap">
				<table class="transaction-table">
					<thead>
						<tr>
							<th scope="col">Settlement Date</th>
							<th scope="col">Transaction Type</th>
							<th scope="col">Portfolio Name</th>
							<th scope="col">ISIN</th>
							<th scope="col">Trade Date</th>
							<th scope="col">Quantity/ Face Value</th>
							<th scope="col">Price</th>
							<th scope="col">PDF Attachment</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="transaction in transactions"
							:key="transaction.name"
							data-testid="transaction-row"
						>
							<td data-label="Settlement Date">
								<RouterLink
									:to="`/transactions/${encodeURIComponent(transaction.name)}`"
									:aria-label="`View transaction ${transaction.name}`"
								>
									{{ formatDate(transaction.settlement_date) }}
								</RouterLink>
								<small>{{ transaction.name }}</small>
							</td>
							<td data-label="Transaction Type">
								{{ transaction.transaction_type }}
							</td>
							<td data-label="Portfolio Name">
								{{ transaction.portfolio_name }}
							</td>
							<td data-label="ISIN">
								{{ transaction.isin }}
							</td>
							<td data-label="Trade Date">
								{{ formatDate(transaction.trade_date) }}
							</td>
							<td data-label="Quantity/ Face Value">
								{{ formatNumber(transaction.quantity_face_value) }}
							</td>
							<td data-label="Price">
								{{ formatNumber(transaction.price, 6) }}
							</td>
							<td data-label="PDF Attachment">
								<PdfAttachmentActions
									:attachment="transaction.attachment"
									:document-label="`transaction ${transaction.name}`"
									file-label="PDF"
								/>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div class="pagination-controls" aria-label="Transaction pages">
				<button
					class="secondary-button"
					type="button"
					:disabled="pagination.start === 0"
					@click="
						loadTransactions(Math.max(0, pagination.start - pagination.page_length))
					"
				>
					Previous
				</button>
				<span>
					{{ pagination.start + 1 }}–{{ pagination.start + transactions.length }}
				</span>
				<button
					class="secondary-button"
					type="button"
					:disabled="!pagination.has_more"
					@click="loadTransactions(pagination.start + pagination.page_length)"
				>
					Next
				</button>
			</div>
		</template>
	</section>
</template>
