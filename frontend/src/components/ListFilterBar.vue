<script setup lang="ts">
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
		<button
			v-for="filter in filters"
			:key="filter.field"
			class="list-filter-chip"
			type="button"
			:aria-label="`Clear ${filter.label} filter`"
			@click="emit('clear', filter.field)"
		>
			<span>{{ filter.label }}</span>
			<strong>{{ filter.value }}</strong>
			<span aria-hidden="true">×</span>
		</button>
		<button class="list-filter-clear" type="button" @click="emit('clearAll')">
			Clear all
		</button>
	</div>
</template>
