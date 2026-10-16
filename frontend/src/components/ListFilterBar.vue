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
	<div
		v-if="filters.length"
		class="mb-3 -mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-gray-5"
		data-testid="active-filters"
	>
		<span class="font-semibold">Filters</span>
		<Button
			v-for="filter in filters"
			:key="filter.field"
			variant="outline"
			size="xs"
			:label="`Clear ${filter.label} filter`"
			@click="emit('clear', filter.field)"
		>
			<span class="inline-flex items-center gap-1">
				<span>{{ filter.label }}</span>
				<strong class="font-semibold">{{ filter.value }}</strong>
				<span aria-hidden="true">×</span>
			</span>
		</Button>
		<Button
			label="Clear all"
			variant="ghost"
			theme="blue"
			size="xs"
			@click="emit('clearAll')"
		/>
	</div>
</template>
