import { defineConfig } from "vitest/config";

// Unit tests for src/lib only; the app build stays in vite.config.ts.
export default defineConfig({
	test: {
		include: ["src/**/*.test.ts"],
		environment: "node",
		clearMocks: true,
		restoreMocks: true,
		unstubGlobals: true,
	},
});
