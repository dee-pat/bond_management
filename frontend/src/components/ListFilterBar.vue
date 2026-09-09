<script setup lang="ts">
import { Button } from "frappe-ui";
import type { ActiveListFilter } from "../types";

defineProps<{
	filters: ActiveListFilter[];
}>();

const emit = defineEmits<{
	clear: [field: string];
	clearAll: [];
}>();
</script>

<template>
	<div v-if="filters.length" class="list-filter-bar" data-testid="active-filters">
		<span class="list-filter-bar__label">Filters</span>
		<Button
			v-for="filter in filters"
			:key="filter.field"
			class="list-filter-chip"
			:label="`Clear ${filter.label} filter`"
			@click="emit('clear', filter.field)"
		>
			<span>{{ filter.label }}</span>
			<strong>{{ filter.value }}</strong>
			<span aria-hidden="true">×</span>
		</Button>
		<Button
			class="list-filter-clear"
			label="Clear all"
			variant="ghost"
			@click="emit('clearAll')"
		/>
	</div>
</template>
