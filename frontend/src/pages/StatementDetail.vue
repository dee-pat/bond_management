<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { Button } from "frappe-ui";
import { ListCell, ListHeaderCell } from "frappe-ui/list";

import DataList from "../components/DataList.vue";
import PdfAttachmentActions from "../components/PdfAttachmentActions.vue";
import { InvestorApiError, redirectToLogin, useInvestorApi } from "../lib/api";
import { formatDate, formatNumber } from "../lib/format";
import type { StatementDetail } from "../types";

const route = useRoute();
const statement = ref<StatementDetail | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const statementName = computed(() => String(route.params.statementName ?? ""));
const api = useInvestorApi();
let latestRequest = 0;

function formatMarketPrice(value: number | null): string {
	return value === null ? "—" : formatNumber(value, 6);
}

async function loadStatement(): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await api.fetchStatement(statementName.value);
		if (requestId === latestRequest) {
			statement.value = response.statement;
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
				? "This statement is unavailable or you do not have permission to view it."
				: "The statement could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

onMounted(() => void loadStatement());
</script>

<template>
	<section class="record-surface" aria-labelledby="statement-detail-title">
		<RouterLink class="back-link" to="/statements"> ← Back to statements </RouterLink>

		<div v-if="loading" class="surface-state" aria-live="polite">Loading statement…</div>

		<div v-else-if="error" class="surface-state surface-state--error" role="alert">
			<p>{{ error }}</p>
			<Button label="Retry" variant="outline" @click="loadStatement" />
		</div>

		<template v-else-if="statement">
			<div class="surface-heading">
				<div>
					<p class="surface-kicker">Statement date</p>
					<h2 id="statement-detail-title">
						{{ formatDate(statement.statement_date) }}
					</h2>
				</div>
				<span class="read-only-badge">Read only</span>
			</div>

			<dl class="record-detail-grid" data-testid="statement-detail">
				<div>
					<dt>Portfolio Name</dt>
					<dd>{{ statement.portfolio_name }}</dd>
				</div>
				<div>
					<dt>Statement Date</dt>
					<dd>{{ formatDate(statement.statement_date) }}</dd>
				</div>
				<div>
					<dt>Market Price Posting</dt>
					<dd>{{ statement.market_price_posting || "—" }}</dd>
				</div>
				<div>
					<dt>Reconciliation Status</dt>
					<dd>{{ statement.reconciliation_status || "—" }}</dd>
				</div>
			</dl>

			<section class="pdf-attachment-section" aria-labelledby="statement-pdf-title">
				<h3 id="statement-pdf-title">PDF Attachment</h3>
				<PdfAttachmentActions
					:attachment="statement.attachment"
					:document-label="`statement dated ${formatDate(statement.statement_date)}`"
					file-label="PDF"
				/>
			</section>

			<section class="pdf-attachment-section" aria-labelledby="reconciliation-report-title">
				<h3 id="reconciliation-report-title">Quantity Reconciliation Report</h3>
				<PdfAttachmentActions
					:attachment="statement.quantity_reconciliation_report"
					:document-label="`statement dated ${formatDate(statement.statement_date)}`"
					file-label="reconciliation report"
				/>
			</section>

			<div class="holding-section">
				<h3>Bond Statement Details</h3>
				<div v-if="statement.bond_statement_details.length === 0" class="surface-state">
					This statement has no bond holdings.
				</div>
				<div v-else>
					<DataList
						:items="statement.bond_statement_details"
						:columns="[
							'minmax(10rem,1fr)',
							'minmax(10rem,1fr)',
							'minmax(12rem,1fr)',
							'minmax(12rem,1fr)',
							'minmax(8rem,1fr)',
						]"
						row-key="isin"
						data-testid="statement-holdings"
					>
						<template #header>
							<ListHeaderCell>ISIN</ListHeaderCell>
							<ListHeaderCell>Quantity</ListHeaderCell>
							<ListHeaderCell>Principal Factor</ListHeaderCell>
							<ListHeaderCell>Market Price</ListHeaderCell>
							<ListHeaderCell>Currency</ListHeaderCell>
						</template>
						<template #row="{ item: holding }">
							<ListCell data-label="ISIN">
								{{ holding.isin }}
							</ListCell>
							<ListCell data-label="Quantity">
								{{ formatNumber(holding.quantity) }}
							</ListCell>
							<ListCell data-label="Principal Factor">
								{{ formatNumber(holding.principal_factor, 6) }}
							</ListCell>
							<ListCell data-label="Market Price">
								{{ formatMarketPrice(holding.market_price) }}
							</ListCell>
							<ListCell data-label="Currency">
								{{ holding.currency }}
							</ListCell>
						</template>
					</DataList>
				</div>
			</div>
		</template>
	</section>
</template>
