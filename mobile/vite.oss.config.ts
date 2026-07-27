import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  root: "oss",
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: "../oss-dist",
    emptyOutDir: true,
  },
});
