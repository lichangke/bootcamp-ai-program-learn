import { configDefaults, defineConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default defineConfig({
  ...viteConfig,
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    exclude: [...configDefaults.exclude, "tests/e2e/**"],
  },
});
