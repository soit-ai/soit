import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) => JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

function reconciliation(groupBy: string, groups: unknown[]) {
  return {
    since: '2026-09-24T09:00:00Z',
    until: null,
    entry_count: 5,
    status_counts: { priced: 2, free: 0, estimated: 1, unpriced: 2 },
    amounts: { USD: '0.500000', CNY: '2.000000' },
    estimated_amounts: { USD: '0.100000' },
    unpriced_reasons: [{ reason: 'pricing_not_configured', entry_count: 2 }],
    group_by: groupBy,
    groups,
    groups_truncated: false,
    external_reconciliation: 'not_performed',
  }
}

const byModel = [
  { key: 'model:deepseek:chat', currency: 'CNY', entry_count: 1, amount: '2.000000', estimated_count: 0, unpriced_count: 0, total_tokens: 10 },
  { key: 'model:deepseek:chat', currency: null, entry_count: 2, amount: null, estimated_count: 0, unpriced_count: 2, total_tokens: 20 },
  { key: 'model:openai:gpt-5.1', currency: 'USD', entry_count: 2, amount: '0.500000', estimated_count: 1, unpriced_count: 0, total_tokens: 20 },
]

const byKey = [
  { key: 'key_a', currency: 'USD', entry_count: 2, amount: '0.500000', estimated_count: 1, unpriced_count: 0, total_tokens: 20 },
]

async function mockReconciliation(page: Page, seen: URL[]) {
  await page.route('**/api/v1/runs/costs/reconciliation**', (route) => {
    const url = new URL(route.request().url())
    seen.push(url)
    const groupBy = url.searchParams.get('group_by') || 'model'
    const groups = groupBy === 'api_key' ? byKey : byModel
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(reconciliation(groupBy, groups)) })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('the costs page shows spend per currency, unpriced entries apart and the bill unchecked', async ({
  page,
}) => {
  const seen: URL[] = []
  await mockReconciliation(page, seen)

  await page.goto('/observe/costs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('2.00 CNY · 0.50 USD')).toBeVisible()
  await expect(page.getByText('Not checked')).toBeVisible()
  const rows = page.locator('tbody tr')
  await expect(rows.first()).toContainText('model:deepseek:chat')
  await expect(rows.first()).toContainText('2.0000 CNY')
  // The unpriced entries of a model are a row of their own, with no amount.
  await expect(rows.nth(1)).toContainText('—')
  await expect(page.getByText('pricing_not_configured')).toBeVisible()
  expect(seen[0].searchParams.get('group_by')).toBe('model')
  expect(seen[0].searchParams.get('since')).toBeTruthy()
})

test('grouping and filters reach the reconciliation request', async ({ page }) => {
  const seen: URL[] = []
  await mockReconciliation(page, seen)

  await page.goto('/observe/costs', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('tbody tr').first()).toContainText('model:deepseek:chat')

  await page.getByRole('button', { name: 'API key' }).click()
  await expect(page.locator('tbody tr').first()).toContainText('key_a')
  await page.getByRole('button', { name: /^Unpriced/ }).click()
  await page.getByRole('button', { name: 'Gateway' }).click()

  await expect.poll(() => seen.at(-1)?.searchParams.get('source')).toBe('gateway')
  const last = seen.at(-1)!
  expect(last.searchParams.get('group_by')).toBe('api_key')
  expect(last.searchParams.get('pricing_status')).toBe('unpriced')
})

test('the Observe panel links to costs', async ({ page }) => {
  await mockReconciliation(page, [])

  await page.goto('/observe/costs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('link', { name: /Costs/ }).first()).toBeVisible()
})
