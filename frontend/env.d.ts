/// <reference types="vite/client" />

declare module "~icons/lucide/*" {
	import type { Component } from "vue";

	const icon: Component;
	export default icon;
}
