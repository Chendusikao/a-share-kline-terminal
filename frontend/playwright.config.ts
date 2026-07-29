import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url));
const pythonCommand =
  process.platform === "win32"
    ? `"${path.resolve(frontendDirectory, "../.venv/Scripts/python.exe")}"`
    : "python";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `${pythonCommand} -m uvicorn tests.support.offline_server:app --host 127.0.0.1 --port 8000`,
    cwd: path.resolve(frontendDirectory, "../backend"),
    url: "http://127.0.0.1:8000/api/v1/health",
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      ...process.env,
      A_SHARE_ALLOW_AKSHARE_NETWORK: "0",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
