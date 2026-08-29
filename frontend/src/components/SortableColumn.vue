<script setup lang="ts">
import { computed } from "vue";
import type { SortOrder } from "../types";

const props = withDefaults(
	defineProps<{
		label: string;
		field: string;
		sortBy: string;
		sortOrder: SortOrder;
		disabled?: boolean;
	}>(),
	{ disabled: false }
);

const emit = defineEmits<{
	sort: [field: string, order: SortOrder];
}>();

const isActive = computed(() => props.sortBy === props.field);
const nextOrder = computed<SortOrder>(() => {
	if (!isActive.value) return "asc";
	return props.sortOrder === "asc" ? "desc" : "asc";
});
const ariaSort = computed(() => {
	if (!isActive.value) return "none";
	return props.sortOrder === "asc" ? "ascending" : "descending";
});

function sortColumn(): void {
	if (!props.disabled) emit("sort", props.field, nextOrder.value);
}
</script>

<template>
	<th scope="col" :aria-label="label" :aria-sort="ariaSort" :data-sort-field="field">
		<button
			class="list-column-button"
			:class="{ 'list-column-button--active': isActive }"
			type="button"
			:disabled="disabled"
			:title="`Sort by ${label} ${nextOrder === 'asc' ? 'ascending' : 'descending'}`"
			@click="sortColumn"
		>
			<span>{{ label }}</span>
			<span class="list-column-button__indicator" aria-hidden="true">
				{{ isActive ? (sortOrder === "asc" ? "↑" : "↓") : "↕" }}
			</span>
		</button>
	</th>
</template>
