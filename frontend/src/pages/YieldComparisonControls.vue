<script setup lang="ts">
import { computed } from "vue";
import { Button, Checkbox } from "frappe-ui";

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
	<fieldset class="yield-comparison-selector" data-testid="yield-comparison-selector">
		<legend>Bonds to compare</legend>
		<Checkbox
			:model-value="allSelected"
			:indeterminate="someSelected"
			class="yield-comparison-selector__all"
			label="Select all bonds"
			@update:model-value="emit('toggleAll', $event)"
		/>
		<span>{{ selected.size }} of {{ bonds.length }} bonds selected</span>
		<div class="yield-comparison-selector__bonds">
			<Checkbox
				v-for="bond in bonds"
				:key="bond.isin"
				:model-value="selected.has(bond.isin)"
				class="yield-comparison-selector__bond"
				@update:model-value="emit('toggleBond', bond.isin, $event)"
			>
				<template #label>
					<span class="sr-only">Select {{ bond.isin }}</span>
					<strong>{{ bond.isin }}</strong>
					<small>{{ bond.currency || "—" }}</small>
				</template>
			</Checkbox>
		</div>
	</fieldset>

	<section class="yield-comparison-audit">
		<Button
			:label="copying ? 'Copying audit data…' : 'Copy audit data to Excel'"
			:disabled="copying"
			variant="outline"
			@click="emit('copy')"
		/>
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
