import { defineConfig, devices } from '@playwright/test'

process.env.NO_PROXY = process.env.NO_PROXY || '127.0.0.1,localhost'

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5000'
const apiBaseURL = process.env.SOIT_REAL_API_BASE_URL || 'http://127.0.0.1:9200/api/v1'

export default defineConfig({
  testDir: './e2e-real',
  timeout: 120 * 1000,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'line',
  outputDir: 'test-results/real-backend',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run build && npm run start',
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 300 * 1000,
    env: {
      VITE_BASE_URL: apiBaseURL,
    },
  },
  projects: [
    {
      name: 'chromium-real-backend',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
