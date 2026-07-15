import { defineConfig, devices } from '@playwright/test'

process.env.NO_PROXY = process.env.NO_PROXY || '127.0.0.1,localhost'

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5000'
const workers = Number(process.env.PLAYWRIGHT_WORKERS || '1')

export default defineConfig({
  testDir: './e2e',
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
    reuseExistingServer: !process.env.CI,
    timeout: 240 * 1000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
