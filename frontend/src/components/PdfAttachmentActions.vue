<script setup lang="ts">
import { Button } from "frappe-ui";

defineProps<{
	attachment: string | null;
	documentLabel: string;
	fileLabel: string;
}>();
</script>

<template>
	<div v-if="attachment" class="flex flex-wrap gap-2">
		<Button
			:link="attachment"
			theme="blue"
			variant="solid"
			size="sm"
			icon-left="lucide-eye"
			target="_blank"
			rel="noopener"
			:aria-label="`View ${documentLabel} ${fileLabel}`"
		>
			View {{ fileLabel }}
		</Button>
		<Button
			:link="attachment"
			theme="gray"
			variant="outline"
			size="sm"
			icon-left="lucide-download"
			download
			target="_self"
			:aria-label="`Download ${documentLabel} ${fileLabel}`"
		>
			Download {{ fileLabel }}
		</Button>
	</div>
	<span v-else class="text-p-sm text-ink-gray-5">No {{ fileLabel }} available</span>
</template>
