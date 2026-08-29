import { defineConfig, devices } from '@playwright/test'

process.env.NO_PROXY = process.env.NO_PROXY || '127.0.0.1,localhost'

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5000'
const workers = Number(process.env.PLAYWRIGHT_WORKERS || '1')

export default defineConfig({
  testDir: './e2e',
  // e2e/legacy holds the specs for the pre-rebuild pages that app/routes_old
  // backs up. They drive URLs the console no longer serves, so they are kept
  // beside that backup rather than run.
  testIgnore: '**/legacy/**',
  timeout: 60 * 1000,
  workers,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run build && npm run start',
    url: baseURL,
    // Never reuse: the command builds, so a reused server keeps serving the
    // previous build and the suite silently tests stale code. That has produced
    // false passes — including tests that asserted UI which had already been
    // deleted — so the rebuild is worth the wait.
    reuseExistingServer: false,
    timeout: 240 * 1000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
