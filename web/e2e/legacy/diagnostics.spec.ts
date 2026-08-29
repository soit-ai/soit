import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from '../helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
  localStorage.setItem('i18nextLng', 'en-US')
}

async function mockCurrentUser(page: Page, role: 'Owner' | 'Viewer') {
  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: {
          id: 'user-1',
          email: 'user@example.com',
          name: 'Workspace user',
          tenant_id: 'tenant-1',
          workspace_id: 'workspace-1',
          tenant_role: role,
          workspace_role: role,
        },
      }),
    })
  })
}

async function mockDiagnostics(page: Page, state: { calls: number }) {
  await page.route('**/api/v1/diagnostics', async (route) => {
    state.calls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: {
          generated_at: `2026-07-18T01:00:0${state.calls}Z`,
          version: '1.0.0',
          environment: 'development',
          overall_status: 'healthy',
          dependencies: [
            { name: 'database', status: 'healthy', latency_ms: 1.25, message: null },
            { name: 'object_storage', status: 'healthy', latency_ms: 2.5, message: null },
          ],
          process: { uptime_seconds: 120, rss_bytes: 134217728, thread_count: 8 },
          workspace: {
            agents: 3,
            workflows: 2,
            knowledge_bases: 1,
            plugins: 4,
            models: 5,
            threads: 6,
            active_runs: 1,
            failed_runs_24h: 2,
            open_feedback: 1,
          },
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
})

test('workspace owner sees and refreshes a live diagnostics snapshot', async ({ page }) => {
  const state = { calls: 0 }
  await mockCurrentUser(page, 'Owner')
  await mockDiagnostics(page, state)

  await page.goto('/diagnostics', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'System diagnostics' })).toBeVisible()
  await expect(page.getByText('Database')).toBeVisible()
  await expect(page.getByText('Object storage')).toBeVisible()
  await expect(page.getByText('128 MB')).toBeVisible()
  await expect(page.getByText('Active runs').locator('..')).toContainText('1')
  await expect(page.getByText('Alert management')).toHaveCount(0)

  await page.getByRole('button', { name: 'Refresh snapshot' }).click()
  await expect.poll(() => state.calls).toBe(2)
})

test('non-owner cannot load diagnostics data', async ({ page }) => {
  const state = { calls: 0 }
  await mockCurrentUser(page, 'Viewer')
  await mockDiagnostics(page, state)

  await page.goto('/diagnostics', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Owner access required' })).toBeVisible()
  expect(state.calls).toBe(0)
})
