import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const port = Number(process.env.E2E_PORT ?? 8765);
const backend = path.resolve(__dirname, "../backend");
const python =
  process.env.PORTAL_PYTHON ??
  path.join(backend, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const samplesDir = path.resolve(__dirname, "e2e/.samples");

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    channel: process.env.PW_CHANNEL || undefined,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${python}" "${path.join(backend, "scripts", "e2e_server.py")}" ${port} "${samplesDir}"`,
    cwd: backend,
    url: `http://127.0.0.1:${port}/healthz`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
