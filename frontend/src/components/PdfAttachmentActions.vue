<script setup lang="ts">
defineProps<{
	attachment: string | null;
	documentLabel: string;
	fileLabel: string;
}>();
</script>

<template>
	<div v-if="attachment" class="pdf-attachment-actions">
		<a
			class="pdf-attachment-link"
			:href="attachment"
			target="_blank"
			rel="noopener"
			:aria-label="`View ${documentLabel} ${fileLabel}`"
		>
			View {{ fileLabel }}
		</a>
		<a
			class="pdf-attachment-link"
			:href="attachment"
			download
			:aria-label="`Download ${documentLabel} ${fileLabel}`"
		>
			Download {{ fileLabel }}
		</a>
	</div>
	<span v-else class="pdf-attachment-empty">No {{ fileLabel }} available</span>
</template>
