import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Backend FastAPI en développement (voir CLAUDE.md).
const BACKEND = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Chemins relatifs : le build est servi par FastAPI et embarqué par PyInstaller.
  base: "./",
  server: {
    proxy: {
      "/api": BACKEND,
      "/ws": { target: BACKEND, ws: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
  },
});
