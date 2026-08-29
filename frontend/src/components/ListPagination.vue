<script setup lang="ts">
import { Button } from "frappe-ui";

withDefaults(
	defineProps<{
		label: string;
		itemCount: number;
		pageLength: number;
		hasMore: boolean;
		loading?: boolean;
		pageLengthOptions?: number[];
	}>(),
	{
		loading: false,
		pageLengthOptions: () => [20, 50],
	}
);

const emit = defineEmits<{
	loadMore: [];
	changePageLength: [pageLength: number];
}>();
</script>

<template>
	<footer class="list-paging-area" :aria-label="label" data-testid="desk-pagination">
		<div class="list-paging-area__summary">
			<strong>{{ itemCount }}</strong>
			<span>{{ itemCount === 1 ? "record" : "records" }} shown</span>
			<span v-if="hasMore" class="list-paging-area__more-hint">More available</span>
		</div>

		<div class="list-paging-area__actions">
			<div class="list-paging-area__sizes" aria-label="Rows per page" role="group">
				<Button
					v-for="option in pageLengthOptions"
					:key="option"
					class="list-paging-area__size"
					:aria-label="`${option} rows per page`"
					:aria-pressed="pageLength === option"
					:disabled="loading || pageLength === option"
					:variant="pageLength === option ? 'solid' : 'outline'"
					:label="`${option} rows per page`"
					@click="emit('changePageLength', option)"
				>
					{{ option }}
				</Button>
			</div>

			<Button
				v-if="hasMore"
				class="list-paging-area__load-more"
				:loading="loading"
				loading-text="Loading"
				label="Load More"
				variant="outline"
				@click="emit('loadMore')"
			/>
		</div>
	</footer>
</template>
