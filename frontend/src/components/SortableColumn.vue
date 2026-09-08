<script setup lang="ts">
import { computed } from "vue";
import { ListHeaderCellSort } from "frappe-ui/list";
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
const direction = computed<SortOrder | null>(() => (isActive.value ? props.sortOrder : null));

function sortColumn(): void {
	if (!props.disabled) emit("sort", props.field, nextOrder.value);
}
</script>

<template>
	<ListHeaderCellSort
		:direction="direction"
		:class="{
			'list-column-button--active': isActive,
			'pointer-events-none opacity-50': disabled,
		}"
		:aria-label="label"
		:data-sort-field="field"
		@click="sortColumn"
	>
		{{ label }}
	</ListHeaderCellSort>
</template>
