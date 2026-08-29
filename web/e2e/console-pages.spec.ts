import { expect, test } from '@playwright/test'

import { mockShellApi } from './helpers'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('overview renders the dashboard and toggles the empty-state demo', async ({ page }) => {
  await page.goto('/v2', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  await expect(page.getByText('1,284')).toBeVisible()
  await expect(page.getByText('96.4%')).toBeVisible()
  // 24 one-hour buckets in the outcome chart.
  await expect(page.locator('.bars .col')).toHaveCount(24)
  await expect(page.getByText('run_01J9KD84QF')).toBeVisible()

  await page.getByRole('button', { name: 'Demo: empty state' }).click()
  await expect(page.getByText('Get your workspace running')).toBeVisible()
  await expect(page.getByText('No runs yet.', { exact: false })).toBeVisible()
})

test('overview recent-run row opens the run detail route', async ({ page }) => {
  await page.goto('/v2', { waitUntil: 'domcontentloaded' })
  await page.getByText('run_01J9KD6H0T').click()
  await expect(page).toHaveURL(/\/v2\/observe\/runs\/run_01J9KD6H0T/)
})

test('knowledge list filters by source kind and opens the library detail', async ({ page }) => {
  await page.goto('/v2/build/knowledge', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('product-docs')).toBeVisible()
  await page.locator('.fchip', { hasText: 'Upload' }).click()
  await expect(page.getByText('support-macros')).toBeVisible()
  await expect(page.getByText('product-docs')).toHaveCount(0)

  await page.locator('.fchip', { hasText: 'All' }).click()
  await page.getByText('product-docs').click()
  await expect(page).toHaveURL(/\/v2\/build\/knowledge\/product-docs/)

  // Detail tabs: retrieval testing shows scored results.
  await page.getByRole('button', { name: 'Retrieval testing' }).click()
  await expect(page.getByText('ck_4a91#13')).toBeVisible()
  await expect(page.getByText('Run query')).toBeVisible()
})

test('plugins installed table filters and flips the enable toggle', async ({ page }) => {
  await page.goto('/v2/build/plugins', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('k8s-toolkit', { exact: true })).toBeVisible()
  await page.locator('.fchip', { hasText: 'Disabled' }).click()
  await expect(page.getByText('cdn-tools', { exact: true })).toBeVisible()
  await expect(page.getByText('k8s-toolkit', { exact: true })).toHaveCount(0)

  const toggle = page.getByRole('switch', { name: 'cdn-tools' })
  await expect(toggle).toHaveAttribute('aria-checked', 'false')
  await toggle.click()
  // Enabling it removes the row from the disabled-only view.
  await expect(page.getByText('cdn-tools', { exact: true })).toHaveCount(0)
  await page.locator('.fchip', { hasText: 'All' }).click()
  await expect(page.getByRole('switch', { name: 'cdn-tools' })).toHaveAttribute('aria-checked', 'true')
})

test('models library filters by capability', async ({ page }) => {
  await page.goto('/v2/build/models', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Anthropic', { exact: true }).first()).toBeVisible()
  await page.getByRole('tab', { name: /Library/ }).click()
  await expect(page.getByText('claude-sonnet-5').first()).toBeVisible()

  await page.locator('.fchip', { hasText: 'Embedding' }).click()
  await expect(page.getByText('bge-m3')).toBeVisible()
  await expect(page.getByText('claude-sonnet-5')).toHaveCount(0)
})

test('chat switches threads and links replies to run evidence', async ({ page }) => {
  await page.goto('/v2/chat', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Chat' })).toBeVisible()
  await expect(page.locator('.thread.on')).toContainText('checkout-api 502s')

  await page.locator('.thread', { hasText: 'vault rotation runbook' }).click()
  await expect(page.locator('.thread.on')).toContainText('vault rotation runbook')

  await page.locator('.evd', { hasText: 'run_01J9KD7Z2M' }).click()
  await expect(page).toHaveURL(/\/v2\/observe\/runs\/run_01J9KD7Z2M/)
})

test('settings redirects to account and navigates sections via the subnav', async ({ page }) => {
  await page.goto('/v2/settings', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/v2\/settings\/account/)
  await expect(page.getByText('Display name')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'Team' }).click()
  await expect(page).toHaveURL(/\/v2\/settings\/team/)
  await expect(page.getByText('audit-bot')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'Billing & license' }).click()
  await expect(page.getByText('INV-2026-0301')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'About' }).click()
  await expect(page.getByText('github.com/soit-ai/soit')).toBeVisible()
})

test('workflow list opens the builder canvas with an inspector', async ({ page }) => {
  await page.goto('/v2/build/workflows', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('ticket-escalation').first()).toBeVisible()
  await page.getByText('docs-nightly-sync').first().click()
  await expect(page).toHaveURL(/\/v2\/build\/workflows\/docs-nightly-sync/)
})
