<script setup lang="ts">
import { Button } from "frappe-ui";

const props = defineProps<{ field: string; label: string; value: unknown }>();
const emit = defineEmits<{ filter: [field: string, label: string, value: unknown] }>();
</script>

<template>
	<Button
		class="list-filter-button"
		variant="ghost"
		size="sm"
		:label="`Filter ${props.label} by ${props.value}`"
		@click="emit('filter', props.field, props.label, props.value)"
	>
		<slot>{{ props.value }}</slot>
	</Button>
</template>
