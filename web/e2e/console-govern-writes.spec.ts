import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

const secrets = [
  {
    id: 'sec_1',
    name: 'k8s-staging',
    description: 'kubeconfig for the staging cluster',
    last_rotated_at: NOW,
    created_at: NOW,
    updated_at: NOW,
  },
]

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('secrets can be created from the console', async ({ page }) => {
  let posted: Record<string, unknown> | null = null
  await json(page, '**/api/v1/secrets?**', secrets)
  await json(page, '**/api/v1/secrets', secrets)
  await page.route('**/api/v1/secrets', async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(secrets) })
    }
    posted = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ id: 'sec_2', name: 'slack-bot-token', created_at: NOW, updated_at: NOW }),
    })
  })

  await page.goto('/govern/secrets', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Add secret' }).click()

  await expect(page.getByRole('heading', { name: 'New secret' })).toBeVisible()
  // Create stays disabled until both the reference and a value are present.
  const create = page.getByRole('button', { name: 'Create' })
  await expect(create).toBeDisabled()

  await page.locator('.console-modal input.input').first().fill('slack-bot-token')
  await page.locator('.console-modal textarea.input').fill('xoxb-not-a-real-token')
  await expect(create).toBeEnabled()
  await create.click()

  await expect.poll(() => posted).not.toBeNull()
  expect(posted).toMatchObject({ name: 'slack-bot-token', value: 'xoxb-not-a-real-token' })
})

test('rotating a secret without a new value leaves the value alone', async ({ page }) => {
  let patched: Record<string, unknown> | null = null
  await json(page, '**/api/v1/secrets**', secrets)
  await page.route('**/api/v1/secrets/sec_1', (route) => {
    patched = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(secrets[0]) })
  })

  await page.goto('/govern/secrets', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Rotate' }).click()

  await page.locator('.console-modal input.input').nth(1).fill('rotated description')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => patched).not.toBeNull()
  expect(patched).toMatchObject({ description: 'rotated description' })
  // No value typed means the key must be absent, not sent empty.
  expect(patched && 'value' in patched).toBe(false)
})

test('policies can be edited and saved from the console', async ({ page }) => {
  let egressPut: Record<string, unknown> | null = null
  let limitsPut: Record<string, unknown> | null = null

  await json(page, '**/api/v1/security/egress/workspace', {
    scope: 'workspace',
    allowlist: ['docs.acme.io'],
    blocklist: [],
  })
  await json(page, '**/api/v1/security/limits/workspace', {
    llm_rate_limit_per_minute: 60,
    tool_rate_limit_per_minute: null,
    llm_daily_quota: null,
    tool_daily_quota: null,
  })
  await json(page, '**/api/v1/security/egress/audits**', {
    items: [],
    next_page_token: null,
    page_size: 20,
  })

  await page.route('**/api/v1/security/egress/workspace', (route) => {
    if (route.request().method() === 'PUT') {
      egressPut = route.request().postDataJSON()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({ scope: 'workspace', allowlist: [], blocklist: [] }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ scope: 'workspace', allowlist: ['docs.acme.io'], blocklist: [] }),
    })
  })
  await page.route('**/api/v1/security/limits/workspace', (route) => {
    if (route.request().method() === 'PUT') {
      limitsPut = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok({}) })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        llm_rate_limit_per_minute: 60,
        tool_rate_limit_per_minute: null,
        llm_daily_quota: null,
        tool_daily_quota: null,
      }),
    })
  })

  await page.goto('/govern/policies', { waitUntil: 'domcontentloaded' })
  // The rule table is built from the live policy, not a fixture.
  await expect(page.getByText('egress.allow:docs.acme.io')).toBeVisible()

  await page.getByRole('button', { name: 'Edit rules' }).click()
  const textareas = page.locator('.console-modal textarea.input')
  await textareas.first().fill('docs.acme.io\napi.acme.io')
  await textareas.nth(1).fill('evil.example')
  await page.locator('.console-modal input.input').first().fill('120')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => egressPut).not.toBeNull()
  expect(egressPut).toMatchObject({
    allowlist: ['docs.acme.io', 'api.acme.io'],
    blocklist: ['evil.example'],
  })
  await expect.poll(() => limitsPut).not.toBeNull()
  // An empty box is no limit — null, not zero.
  expect(limitsPut).toMatchObject({
    llm_rate_limit_per_minute: 120,
    tool_rate_limit_per_minute: null,
    llm_daily_quota: null,
  })
})
