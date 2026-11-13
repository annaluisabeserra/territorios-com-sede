import { defineConfig, devices } from "@playwright/test";

// Local: usa o Chromium pré-instalado se PW_CHROMIUM_PATH estiver definido. CI: `npx playwright install chromium`.
const executablePath = process.env.PW_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:4322", trace: "off", launchOptions: { executablePath } },
  webServer: { command: "npx astro preview --port 4322", port: 4322, reuseExistingServer: true, timeout: 60_000 },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } } },
    { name: "celular", use: { ...devices["Pixel 7"], launchOptions: { executablePath } } },
  ],
});
