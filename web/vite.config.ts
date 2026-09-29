import { defineConfig } from "vitest/config";

// Relative asset paths, so the site works under GitHub Pages' /<repo>/ prefix too.
export default defineConfig({
  base: "./",
});
