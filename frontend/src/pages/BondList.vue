<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { fetchBonds, InvestorApiError, redirectToLogin } from "../lib/api";
import { formatDate } from "../lib/format";
import type { BondListRow, BondPage } from "../types";

const bonds = ref<BondListRow[]>([]);
const pagination = ref<BondPage["pagination"]>({
	start: 0,
	page_length: 20,
	has_more: false,
});
const loading = ref(true);
const error = ref<string | null>(null);
let latestRequest = 0;

async function loadBonds(start = 0): Promise<void> {
	const requestId = ++latestRequest;
	loading.value = true;
	error.value = null;

	try {
		const response = await fetchBonds({
			start,
			pageLength: pagination.value.page_length,
		});
		if (requestId !== latestRequest) {
			return;
		}
		bonds.value = response.data;
		pagination.value = response.pagination;
	} catch (caughtError) {
		if (requestId !== latestRequest) {
			return;
		}
		if (caughtError instanceof InvestorApiError && caughtError.status === 401) {
			redirectToLogin();
			return;
		}
		error.value = "Bonds could not be loaded. Please retry.";
	} finally {
		if (requestId === latestRequest) {
			loading.value = false;
		}
	}
}

onMounted(() => void loadBonds());
</script>

<template>
  <section
    class="record-surface"
    aria-labelledby="bond-list-title"
  >
    <div class="surface-heading">
      <div>
        <p class="surface-kicker">
          Shared reference data
        </p>
        <h2 id="bond-list-title">
          Bond catalog
        </h2>
      </div>
    </div>

    <div
      v-if="loading"
      class="surface-state"
      aria-live="polite"
    >
      Loading bonds…
    </div>

    <div
      v-else-if="error"
      class="surface-state surface-state--error"
      role="alert"
    >
      <p>{{ error }}</p>
      <button
        class="secondary-button"
        type="button"
        @click="loadBonds(pagination.start)"
      >
        Retry
      </button>
    </div>

    <div
      v-else-if="bonds.length === 0"
      class="surface-state"
      data-testid="bonds-empty"
    >
      No bonds are available.
    </div>

    <template v-else>
      <div class="record-table-wrap">
        <table class="record-table">
          <thead>
            <tr>
              <th scope="col">
                Bond Name
              </th>
              <th scope="col">
                ISIN
              </th>
              <th scope="col">
                Currency
              </th>
              <th scope="col">
                Issue Date
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="bond in bonds"
              :key="bond.name"
              data-testid="bond-row"
            >
              <td data-label="Bond Name">
                <RouterLink
                  :to="`/bonds/${encodeURIComponent(bond.name)}`"
                  :aria-label="`View bond ${bond.name}`"
                >
                  {{ bond.bond_name }}
                </RouterLink>
              </td>
              <td data-label="ISIN">
                {{ bond.isin }}
              </td>
              <td data-label="Currency">
                {{ bond.currency }}
              </td>
              <td data-label="Issue Date">
                {{ formatDate(bond.issue_date) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        class="pagination-controls"
        aria-label="Bond pages"
      >
        <button
          class="secondary-button"
          type="button"
          :disabled="pagination.start === 0"
          @click="loadBonds(Math.max(0, pagination.start - pagination.page_length))"
        >
          Previous
        </button>
        <span>{{ pagination.start + 1 }}–{{ pagination.start + bonds.length }}</span>
        <button
          class="secondary-button"
          type="button"
          :disabled="!pagination.has_more"
          @click="loadBonds(pagination.start + pagination.page_length)"
        >
          Next
        </button>
      </div>
    </template>
  </section>
</template>
