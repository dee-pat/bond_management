import { createApp, nextTick } from "vue";
import { afterEach } from "vitest";

const unmountAll: Array<() => void> = [];

afterEach(() => {
	unmountAll.splice(0).forEach((unmount) => unmount());
});

// Vue's testing guide: run a composable that uses lifecycle hooks inside a host app.
export function withSetup<T>(composable: () => T): T {
	let result!: T;
	const app = createApp({
		setup() {
			result = composable();
			return () => null;
		},
	});
	app.mount(document.createElement("div"));
	unmountAll.push(() => app.unmount());
	return result;
}

export async function settle(): Promise<void> {
	await new Promise((resolve) => setTimeout(resolve, 0));
	await nextTick();
}
