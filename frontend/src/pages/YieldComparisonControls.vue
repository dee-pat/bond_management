<script setup lang="ts">
import { computed } from "vue";

interface BondChoice {
	isin: string;
	currency: string;
}

const props = defineProps<{
	bonds: BondChoice[];
	selectedIsins: string[];
	copying: boolean;
	copyFeedback: { kind: "error" | "success"; message: string } | null;
}>();
const emit = defineEmits<{
	toggleAll: [checked: boolean];
	toggleBond: [isin: string, checked: boolean];
	copy: [];
}>();
const selected = computed(() => new Set(props.selectedIsins));
const allSelected = computed(
	() => props.bonds.length > 0 && selected.value.size === props.bonds.length
);
const someSelected = computed(
	() => selected.value.size > 0 && selected.value.size < props.bonds.length
);
</script>

<template>
  <fieldset
    class="yield-comparison-selector"
    data-testid="yield-comparison-selector"
  >
    <legend>Bonds to compare</legend>
    <label class="yield-comparison-selector__all">
      <input
        :checked="allSelected"
        :indeterminate.prop="someSelected"
        type="checkbox"
        @change="emit('toggleAll', ($event.currentTarget as HTMLInputElement).checked)"
      >
      Select all bonds
    </label>
    <span>{{ selected.size }} of {{ bonds.length }} bonds selected</span>
    <div class="yield-comparison-selector__bonds">
      <label
        v-for="bond in bonds"
        :key="bond.isin"
      >
        <input
          :checked="selected.has(bond.isin)"
          :aria-label="`Select ${bond.isin}`"
          type="checkbox"
          @change="
            emit(
              'toggleBond',
              bond.isin,
              ($event.currentTarget as HTMLInputElement).checked
            )
          "
        >
        <strong>{{ bond.isin }}</strong>
        <small>{{ bond.currency || "—" }}</small>
      </label>
    </div>
  </fieldset>

  <section class="yield-comparison-audit">
    <button
      class="secondary-button"
      type="button"
      :disabled="copying"
      @click="emit('copy')"
    >
      {{ copying ? "Copying audit data…" : "Copy audit data to Excel" }}
    </button>
    <p>Copies Date, ISIN, CCY, Market Price and stored Future XIRR.</p>
    <p
      v-if="copyFeedback"
      class="performance-copy-feedback"
      :class="`performance-copy-feedback--${copyFeedback.kind}`"
      :role="copyFeedback.kind === 'error' ? 'alert' : 'status'"
    >
      {{ copyFeedback.message }}
    </p>
  </section>
</template>
