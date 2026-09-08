<script setup lang="ts" generic="T">
import {
	List,
	ListCell,
	ListHeader,
	ListRow,
	ListRows,
} from "frappe-ui/list";

defineProps<{
	items: T[];
	columns: string[];
	rowKey?: string | ((item: T, index: number) => PropertyKey);
	rowTestId?: string | ((item: T, index: number) => string | undefined);
	rowClass?:
		| string
		| Record<string, boolean>
		| ((item: T, index: number) => string | Record<string, boolean>);
}>();

defineSlots<{
	header?: () => unknown;
	row?: (props: { item: T; index: number; value: string }) => unknown;
}>();
</script>

<template>
	<div class="record-list-wrap">
		<List :columns="columns" divider="full" class="record-list">
			<ListHeader>
				<slot name="header" />
			</ListHeader>
			<ListRows v-slot="{ item, index, value }" :items="items" :row-key="rowKey">
				<div
					class="record-list__row-wrapper"
					:class="typeof rowClass === 'function' ? rowClass(item, index) : rowClass"
					:data-testid="
						typeof rowTestId === 'function' ? rowTestId(item, index) : rowTestId
					"
				>
					<ListRow :value="value">
						<slot name="row" :item="item" :index="index" :value="value">
							<ListCell>{{ item }}</ListCell>
						</slot>
					</ListRow>
				</div>
			</ListRows>
		</List>
	</div>
</template>
