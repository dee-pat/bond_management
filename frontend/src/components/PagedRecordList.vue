<script setup lang="ts" generic="Row">
import DataList from "./DataList.vue";
import ListPagination from "./ListPagination.vue";
import SortableColumn from "./SortableColumn.vue";
import SurfaceState from "./SurfaceState.vue";
import type { PagedList } from "../lib/list";

const props = defineProps<{
	list: PagedList<Row>;
	columns: string[];
	sortColumns: { label: string; field: string }[];
	rowTestId: string;
	loadingText: string;
	emptyText: string;
	emptyTestId: string;
	paginationLabel: string;
	unassigned?: boolean;
}>();

defineSlots<{
	row: (props: { item: Row }) => unknown;
}>();

// The list object is created once by the page, so its refs can be unwrapped here.
const { rows, loading, error, pagination, sortBy, sortOrder } = props.list;
</script>

<template>
	<SurfaceState
		v-if="loading && rows.length === 0"
		:loading="loading"
		:loading-text="loadingText"
	/>

	<SurfaceState v-else-if="error && rows.length === 0" :error="error" @retry="list.retry" />

	<div v-else-if="unassigned" class="surface-state" :data-testid="emptyTestId">
		No portfolios are assigned to your account.
	</div>

	<div v-else-if="rows.length === 0" class="surface-state" :data-testid="emptyTestId">
		{{ emptyText }}
	</div>

	<template v-else>
		<SurfaceState v-if="error" :error="error" @retry="list.retry" />

		<DataList :items="rows" :columns="columns" row-key="name" :row-test-id="rowTestId">
			<template #header>
				<SortableColumn
					v-for="column in sortColumns"
					:key="column.field"
					:label="column.label"
					:field="column.field"
					:sort-by="sortBy"
					:sort-order="sortOrder"
					:disabled="loading"
					@sort="list.changeSort"
				/>
			</template>
			<template #row="{ item }">
				<slot name="row" :item="item" />
			</template>
		</DataList>

		<ListPagination
			:has-more="pagination.has_more"
			:item-count="rows.length"
			:loading="loading"
			:page-length="pagination.page_length"
			:label="paginationLabel"
			@change-page-length="list.changePageLength"
			@load-more="list.loadMore"
		/>
	</template>
</template>
