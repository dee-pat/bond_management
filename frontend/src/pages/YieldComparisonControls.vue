<script setup lang="ts">
import { Button, ErrorMessage } from "frappe-ui";

const props = defineProps<{
	copying: boolean;
	copyFeedback: { kind: "error" | "success"; message: string } | null;
}>();
const emit = defineEmits<{
	copy: [];
}>();
</script>

<template>
	<section class="yield-comparison-audit">
		<Button
			label="Copy audit data to Excel"
			:loading="copying"
			loading-text="Copying audit data…"
			:disabled="copying"
			variant="outline"
			@click="emit('copy')"
		/>
		<p>Copies Date, ISIN, CCY, Market Price and stored Future XIRR.</p>
		<ErrorMessage
			v-if="copyFeedback?.kind === 'error'"
			class="performance-copy-feedback performance-copy-feedback--error"
			:message="copyFeedback.message"
		/>
		<p
			v-else-if="copyFeedback"
			class="performance-copy-feedback"
			:class="`performance-copy-feedback--${copyFeedback.kind}`"
			role="status"
		>
			{{ copyFeedback.message }}
		</p>
	</section>
</template>
