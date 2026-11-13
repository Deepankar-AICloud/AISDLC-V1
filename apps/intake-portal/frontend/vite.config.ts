import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = process.env.PORTAL_BACKEND ?? "http://127.0.0.1:8000";
const proxied = ["/api", "/auth", "/dev", "/healthz"];

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: Object.fromEntries(proxied.map((p) => [p, { target: backend, changeOrigin: false }])),
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 3000,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
