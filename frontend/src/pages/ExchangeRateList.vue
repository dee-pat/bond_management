<script setup lang="ts">
import { RouterLink } from "vue-router";
import { Button } from "frappe-ui";
import { ListCell } from "frappe-ui/list";

import ListFilterBar from "../components/ListFilterBar.vue";
import PagedRecordList from "../components/PagedRecordList.vue";
import FilterButton from "../components/FilterButton.vue";
import { useInvestorApi } from "../lib/api";
import { usePagedList } from "../lib/list";
import { formatDate, formatNumber } from "../lib/format";
import type { ExchangeRateListRow } from "../types";

const api = useInvestorApi();
const list = usePagedList<ExchangeRateListRow>({
	fetchPage: api.fetchExchangeRates,
	sortBy: "rate_date",
	errorMessage: "Exchange rates could not be loaded. Please retry.",
});
const { activeFilter, applyFilter, clearFilter } = list;
const sortColumns = [
	{ label: "Rate Date", field: "rate_date" },
	{ label: "From Currency", field: "from_currency" },
	{ label: "To Currency", field: "to_currency" },
	{ label: "Rate", field: "rate" },
	{ label: "Reverse Rate", field: "reverse_rate" },
];
</script>

<template>
	<section class="record-surface" aria-label="Bond exchange rate list">
		<ListFilterBar
			:filters="activeFilter ? [activeFilter] : []"
			@clear="clearFilter"
			@clear-all="clearFilter"
		/>

		<PagedRecordList
			:list="list"
			:columns="[
				'minmax(9rem,1fr)',
				'minmax(10rem,1fr)',
				'minmax(9rem,1fr)',
				'minmax(10rem,1fr)',
				'minmax(10rem,1fr)',
			]"
			:sort-columns="sortColumns"
			row-test-id="exchange-rate-row"
			loading-text="Loading exchange rates…"
			empty-text="No exchange rates match the selected filters."
			empty-test-id="exchange-rates-empty"
			pagination-label="Exchange rate list pagination"
		>
			<template #row="{ item: exchangeRate }">
				<ListCell data-label="Rate Date">
					<span>{{ formatDate(exchangeRate.rate_date) }}</span>
				</ListCell>
				<ListCell data-label="From Currency">
					<RouterLink
						:to="`/exchange-rates/${encodeURIComponent(exchangeRate.name)}`"
						:aria-label="`View exchange rate ${exchangeRate.name}`"
					>
						{{ exchangeRate.from_currency }}
					</RouterLink>
					<Button
						class="list-filter-action"
						variant="ghost"
						size="sm"
						:label="`Filter From Currency by ${exchangeRate.from_currency}`"
						@click="
							applyFilter(
								'from_currency',
								'From Currency',
								exchangeRate.from_currency
							)
						"
					>
						Filter
					</Button>
				</ListCell>
				<ListCell data-label="To Currency">
					<FilterButton
						field="to_currency"
						label="To Currency"
						:value="exchangeRate.to_currency"
						@filter="applyFilter"
					/>
				</ListCell>
				<ListCell data-label="Rate">
					<FilterButton
						field="rate"
						label="Rate"
						:value="exchangeRate.rate"
						@filter="applyFilter"
					>
						{{ formatNumber(exchangeRate.rate, 12) }}
					</FilterButton>
				</ListCell>
				<ListCell data-label="Reverse Rate">
					<FilterButton
						field="reverse_rate"
						label="Reverse Rate"
						:value="exchangeRate.reverse_rate"
						@filter="applyFilter"
					>
						{{ formatNumber(exchangeRate.reverse_rate, 12) }}
					</FilterButton>
				</ListCell>
			</template>
		</PagedRecordList>
	</section>
</template>
