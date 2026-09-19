// Playwright configuration for the headless-browser accessibility harness.
//
// The webServer starts src-tauri/ui/a11y/serve.mjs on a fixed local port
// and the spec navigates to the served /a11y/ page, which loads
// bundle.a11y.js. The port is taken from the A11Y_PORT env var so the same
// value is used by serve.mjs and Playwright.

import { defineConfig, devices } from '@playwright/test';

const PORT = Number.parseInt(process.env.A11Y_PORT ?? '4173', 10);
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: '.',
  testMatch: 'reference-controls.spec.ts',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE_URL,
    headless: true,
    actionTimeout: 10_000,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'node ./serve.mjs',
    url: `${BASE_URL}/a11y/`,
    timeout: 30_000,
    stdout: 'pipe',
    stderr: 'pipe',
    reuseExistingServer: !process.env.CI,
  },
});
