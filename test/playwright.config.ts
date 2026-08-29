import { defineConfig, devices } from "@playwright/test";
import { rmSync } from "node:fs";
import path from "node:path";

/**
 * Two run modes (PLAN.md section 12):
 *  - BASE_URL set: run against an already-running app (docker-compose.test.yml).
 *  - BASE_URL unset: start the backend locally on E2E_PORT against a fresh
 *    SQLite file, serving the built frontend export from frontend/out.
 */
const repoRoot = path.resolve(__dirname, "..");
const port = Number(process.env.E2E_PORT ?? 8000);
const external = Boolean(process.env.BASE_URL);
const baseURL = process.env.BASE_URL ?? `http://localhost:${port}`;
const dbPath = path.join(__dirname, ".tmp", "e2e.db");

// The config is re-evaluated in each worker process; only the runner process
// (which is also the one that starts the server) may clear the database file.
if (!external && process.env.TEST_WORKER_INDEX === undefined) {
  rmSync(path.join(__dirname, ".tmp"), { recursive: true, force: true });
}

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    viewport: { width: 1600, height: 900 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: external
    ? undefined
    : {
        command: `uv run uvicorn app.main:app --port ${port}`,
        cwd: path.join(repoRoot, "backend"),
        url: `${baseURL}/api/health`,
        reuseExistingServer: false,
        stdout: "pipe",
        stderr: "pipe",
        env: {
          LLM_MOCK: "true",
          MASSIVE_API_KEY: "",
          FINALLY_DB_PATH: dbPath,
          FINALLY_STATIC_DIR: path.join(repoRoot, "frontend", "out"),
        },
      },
});
