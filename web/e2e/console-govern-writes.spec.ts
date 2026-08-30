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

test('a policy revision can be compared and restored', async ({ page }) => {
  let rollback: string | null = null

  const revisions = [
    {
      id: 'pr_2',
      scope: 'workspace',
      scope_id: 'w_1',
      revision: 2,
      bundle_id: 'pb_2222222222222222',
      document: {
        egress_allowlist: ['docs.acme.io', 'api.acme.io'],
        egress_blocklist: [],
        llm_rate_limit_per_minute: 60,
        tool_rate_limit_per_minute: null,
        llm_daily_quota: null,
        tool_daily_quota: null,
      },
      note: null,
      restored_from_revision: null,
      created_by: 'u_1',
      created_at: NOW,
      active: true,
    },
    {
      id: 'pr_1',
      scope: 'workspace',
      scope_id: 'w_1',
      revision: 1,
      bundle_id: 'pb_1111111111111111',
      document: {
        egress_allowlist: ['docs.acme.io'],
        egress_blocklist: [],
        llm_rate_limit_per_minute: 60,
        tool_rate_limit_per_minute: null,
        llm_daily_quota: null,
        tool_daily_quota: null,
      },
      note: null,
      restored_from_revision: null,
      created_by: 'u_1',
      created_at: NOW,
      active: false,
    },
  ]

  await json(page, '**/api/v1/security/egress/workspace', {
    scope: 'workspace',
    allowlist: ['docs.acme.io', 'api.acme.io'],
    blocklist: [],
  })
  await json(page, '**/api/v1/security/limits/workspace', {
    llm_rate_limit_per_minute: 60,
    tool_rate_limit_per_minute: null,
    llm_daily_quota: null,
    tool_daily_quota: null,
  })
  await json(page, '**/api/v1/security/policies/bundle**', {
    scope: 'workspace',
    scope_id: 'w_1',
    bundle_id: 'pb_2222222222222222',
    revision: 2,
    document: revisions[0].document,
    activated_at: NOW,
    activated_by: 'u_1',
  })
  await json(page, '**/api/v1/security/policies/revisions?**', {
    items: revisions,
    next_page_token: null,
    page_size: 25,
  })
  await json(page, '**/api/v1/security/policies/revisions/diff**', {
    scope: 'workspace',
    from_revision: 1,
    to_revision: 2,
    from_bundle_id: 'pb_1111111111111111',
    to_bundle_id: 'pb_2222222222222222',
    changes: [
      {
        field: 'egress_allowlist',
        before: ['docs.acme.io'],
        after: ['docs.acme.io', 'api.acme.io'],
      },
    ],
  })
  await page.route('**/api/v1/security/policies/revisions/pr_1/rollback', (route) => {
    rollback = route.request().url()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        scope: 'workspace',
        scope_id: 'w_1',
        bundle_id: 'pb_1111111111111111',
        revision: 3,
        document: revisions[1].document,
        activated_at: NOW,
        activated_by: 'u_1',
      }),
    })
  })

  await page.goto('/govern/policies', { waitUntil: 'domcontentloaded' })
  // The active-bundle tile reads the revision in force, not a fixture.
  await expect(page.locator('.tile').filter({ hasText: 'Active bundle' })).toContainText('r2')

  await page.getByRole('tab', { name: /^Revisions/ }).click()
  const superseded = page.locator('.bundle').filter({ hasText: 'SUPERSEDED' })
  await expect(superseded).toBeVisible()

  // Selecting the newest revision shows what that save changed.
  await page.locator('.bundle').filter({ hasText: 'r2' }).click()
  await expect(page.getByText('egress_allowlist: docs.acme.io →')).toBeVisible()

  await superseded.click()
  await superseded.getByRole('button', { name: 'Restore' }).click()
  await expect(page.getByRole('heading', { name: 'Restore this revision' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Restore' }).click()

  await expect.poll(() => rollback).not.toBeNull()
  expect(rollback).toContain('/security/policies/revisions/pr_1/rollback')
})
