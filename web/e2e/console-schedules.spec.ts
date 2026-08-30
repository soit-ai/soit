import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string | RegExp, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-30T13:00:00Z'
const SOON = '2026-08-30T14:00:00Z'

const schedule = {
  id: 'sch_1',
  name: 'hourly-billing-audit',
  description: 'usage reconciliation',
  target_kind: 'agent',
  target_id: 'billing-audit',
  inputs: {},
  cron: '0 * * * *',
  timezone: 'UTC',
  enabled: true,
  catch_up: false,
  next_fire_at: SOON,
  last_fired_at: NOW,
  last_run_id: 'run_01J9KD6H0T',
  last_status: 'started',
  last_error: null,
  created_at: NOW,
  updated_at: NOW,
}

const paused = {
  ...schedule,
  id: 'sch_2',
  name: 'weekly-quota-report',
  cron: '0 9 * * 1',
  enabled: false,
  next_fire_at: null,
  last_run_id: null,
  last_status: null,
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('the schedules page lists what the server holds', async ({ page }) => {
  await json(page, '**/api/v1/schedules**', [schedule, paused])

  await page.goto('/execute/schedules', { waitUntil: 'domcontentloaded' })

  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(2)
  await expect(rows.first()).toContainText('hourly-billing-audit')
  await expect(rows.first()).toContainText('0 * * * *')
  // The last firing links to the run it started.
  await expect(rows.first().getByRole('link', { name: 'run_01J9KD6H0T' })).toBeVisible()
})

test('a paused schedule says so instead of showing a next firing', async ({ page }) => {
  await json(page, '**/api/v1/schedules**', [paused])

  await page.goto('/execute/schedules', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('tbody tr').first()).toContainText('paused')
  await expect(page.locator('tbody tr').first()).toContainText('NEVER RUN')
})

test('toggling a schedule patches it rather than changing only the switch', async ({ page }) => {
  await json(page, '**/api/v1/schedules?**', [schedule])

  let patched: unknown = null
  await page.route('**/api/v1/schedules/sch_1', async (route) => {
    patched = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...schedule, enabled: false, next_fire_at: null }),
    })
  })

  await page.goto('/execute/schedules', { waitUntil: 'domcontentloaded' })
  await page.locator('tbody tr').first().locator('[role="switch"], .toggle, button').first().click()

  await expect.poll(() => patched).toEqual({ enabled: false })
})

test('running a schedule now goes through the run endpoint', async ({ page }) => {
  await json(page, '**/api/v1/schedules?**', [schedule])

  let ran = false
  await page.route('**/api/v1/schedules/sch_1/run', (route) => {
    ran = true
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok(schedule),
    })
  })

  await page.goto('/execute/schedules', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Run now' }).click()

  await expect.poll(() => ran).toBe(true)
})

test('the new-schedule dialog previews the expression before it is saved', async ({ page }) => {
  await json(page, '**/api/v1/schedules?**', [])
  await json(page, '**/api/v1/schedules/preview', {
    fires_at: ['2026-08-30T14:00:00Z', '2026-08-30T15:00:00Z', '2026-08-30T16:00:00Z'],
  })

  let created: unknown = null
  await page.route('**/api/v1/schedules', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    created = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({ status: 201, contentType: 'application/json', body: ok(schedule) })
  })

  await page.goto('/execute/schedules', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New schedule' }).click()

  // The next firings are shown for whatever is typed, so a wrong expression is
  // visible before it is saved rather than at two in the morning.
  await expect(page.locator('.console-modal')).toContainText('2026-08-30T14:00:00Z')

  await page.locator('#schedule-name').fill('nightly-docs-sync')
  await page.locator('#schedule-target').fill('docs-nightly-sync')
  await page.locator('#schedule-cron').fill('0 2 * * *')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect.poll(() => created).toMatchObject({
    name: 'nightly-docs-sync',
    target_kind: 'agent',
    target_id: 'docs-nightly-sync',
    cron: '0 2 * * *',
  })
})

test('an expression the server cannot parse is called out in the dialog', async ({ page }) => {
  await json(page, '**/api/v1/schedules?**', [])
  await page.route('**/api/v1/schedules/preview', (route) =>
    route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'VALIDATION_ERROR', message: 'bad cron' }),
    }),
  )

  await page.goto('/execute/schedules', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New schedule' }).click()
  await page.locator('#schedule-cron').fill('every tuesday')

  await expect(page.locator('.console-modal')).toContainText('cannot be parsed')
})
