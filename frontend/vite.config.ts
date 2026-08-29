import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import frappeui from "frappe-ui/vite";

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
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
    },
  },
  server: {
    allowedHosts: ["localhost", "127.0.0.1", "test_site"],
  },
});
