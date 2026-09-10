<script setup lang="ts">
import { Button, ErrorMessage, LoadingText } from "frappe-ui";

withDefaults(
	defineProps<{
		loading?: boolean;
		loadingText?: string;
		error?: string | null;
		testId?: string | null;
	}>(),
	{
		loading: false,
		loadingText: "Loading...",
		error: null,
		testId: null,
	}
);

const emit = defineEmits<{
	retry: [];
}>();
</script>

<template>
	<div v-if="loading" class="surface-state" aria-live="polite" :data-testid="testId">
		<LoadingText :text="loadingText" />
	</div>

	<div v-else-if="error" class="surface-state surface-state--error" :data-testid="testId">
		<ErrorMessage :message="error" />
		<Button label="Retry" variant="outline" @click="emit('retry')" />
	</div>
</template>
