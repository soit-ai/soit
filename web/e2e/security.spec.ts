import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

type EgressPayload = {
  allowlist: string[]
  blocklist: string[]
}

async function mockSettingsApi(page: Page, state: { savedEgressPayload: EgressPayload | null }) {
  await page.route('**/api/v1/api-keys**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [],
          page_size: 100,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/security/limits/workspace', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          scope: 'workspace',
          llm_rate_limit_per_minute: 60,
          tool_rate_limit_per_minute: 120,
          llm_daily_quota: 1000,
          tool_daily_quota: 2000,
        },
      }),
    })
  })

  await page.route('**/api/v1/security/egress/workspace', async (route) => {
    if (route.request().method() === 'PUT') {
      const payload = JSON.parse(route.request().postData() || '{}') as EgressPayload
      state.savedEgressPayload = payload
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            scope: 'workspace',
            ...payload,
          },
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          scope: 'workspace',
          allowlist: ['api.initial.example'],
          blocklist: ['*.blocked.initial'],
        },
      }),
    })
  })

  await page.route('**/api/v1/security/egress/audits**', async (route) => {
    const allowlist = state.savedEgressPayload?.allowlist || ['api.initial.example']
    const blocklist = state.savedEgressPayload?.blocklist || ['*.blocked.initial']
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [
            {
              id: 'audit-1',
              tenant_id: 'tenant-1',
              workspace_id: 'workspace-1',
              scope: 'workspace',
              allowlist,
              blocklist,
              created_by: 'user-1',
              created_at: '2026-05-01T10:00:00.000Z',
            },
          ],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
})

test('workspace egress policy can be edited from settings', async ({ page }) => {
  const state: { savedEgressPayload: EgressPayload | null } = { savedEgressPayload: null }
  await mockSettingsApi(page, state)

  await page.goto('/settings/api', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: '出口策略' }).click()

  await expect(page.getByLabel('允许域名')).toHaveValue('api.initial.example')
  await page.getByLabel('允许域名').fill('api.example.com\n*.trusted.internal')
  await page.getByLabel('阻断域名').fill('*.blocked.example')
  await page.getByRole('button', { name: '保存出口策略' }).click()

  await expect.poll(() => state.savedEgressPayload).toEqual({
    allowlist: ['api.example.com', '*.trusted.internal'],
    blocklist: ['*.blocked.example'],
  })

  const auditRow = page.getByRole('row').filter({ hasText: 'user-1' })
  await expect(auditRow).toBeVisible()
  await expect(auditRow.getByRole('cell', { name: '2', exact: true })).toBeVisible()
  await expect(auditRow.getByRole('cell', { name: '1', exact: true })).toBeVisible()
})

test('community settings do not simulate security, privacy, or billing operations', async ({ page }) => {
  await page.goto('/settings/security', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Community 1.0 security scope')).toBeVisible()
  await expect(page.getByText('Chrome / Windows')).toHaveCount(0)
  await expect(page.getByText('ABCD EFGH IJKL MNOP')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /sign out other sessions/i })).toHaveCount(0)

  await page.goto('/settings/privacy', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Self-service privacy operations are unavailable')).toBeVisible()
  await expect(page.getByRole('button', { name: /export|delete/i })).toHaveCount(0)

  await page.goto('/settings/billing', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Billing is not part of SOIT Community')).toBeVisible()
  await expect(page.getByText('4242')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /upgrade|payment|invoice/i })).toHaveCount(0)

  await page.goto('/settings/analytics', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Preference and export APIs are unavailable')).toBeVisible()
  await expect(page.getByRole('button', { name: /save|export/i })).toHaveCount(0)

  await page.goto('/settings/about', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Community build')).toBeVisible()
  await expect(page.getByText('张三')).toHaveCount(0)
  await expect(page.getByText('2025-05-30')).toHaveCount(0)
})
