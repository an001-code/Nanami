import { resolve } from "node:path";
import { defineConfig } from "vite";

const rootDir = resolve(import.meta.dirname);

export default defineConfig({
  base: "./",
  build: {
    outDir: "dist-nanami",
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(rootDir, "src/nanami-index.html")
    }
  }
});
