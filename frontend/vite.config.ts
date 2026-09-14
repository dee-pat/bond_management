import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import frappeui from "frappe-ui/vite";

const frappeUiUtils = new URL("./node_modules/frappe-ui/src/utils", import.meta.url).pathname;

export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: "/bond-investor",
      frappeProxy: {
        source: "^/(api|assets|files|private|login)",
      },
      jinjaBootData: true,
      buildConfig: {
        baseUrl: "/assets/bond_management/frontend/",
        emptyOutDir: true,
        indexHtmlPath: "../bond_management/www/bond-investor.html",
        sourcemap: true,
      },
    }),
    vue(),
  ],
  build: {
    target: "es2015",
  },
  optimizeDeps: {
    exclude: ["frappe-ui"],
  },
  resolve: {
    alias: [
      {
        find: /^#utils\/(.+)$/,
        replacement: `${frappeUiUtils}/$1.ts`,
      },
      {
        find: "@",
        replacement: new URL("./src", import.meta.url).pathname,
      },
    ],
  },
  server: {
    allowedHosts: ["localhost", "127.0.0.1", "test_site"],
  },
});
