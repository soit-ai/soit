import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

/** mockShellApi answers /me with user-1 in workspace-1. */
const members = [
  { user_id: 'user-1', email: 'zzpd106@gmail.com', name: 'Jude', role: 'Owner', status: 'active' },
  { user_id: 'u_2', email: 'wei@acme.io', name: 'Wei', role: 'Viewer', status: 'active' },
]

const apiKeys = {
  items: [
    {
      id: 'key_1',
      tenant_id: 't1',
      workspace_id: 'workspace-1',
      user_id: 'user-1',
      name: 'ci-pipeline',
      key_prefix: 'sk_fixture_a',
      status: 'active',
      scopes: ['read'],
      expires_at: null,
      last_used_at: NOW,
      revoked_at: null,
      created_at: NOW,
      updated_at: NOW,
    },
  ],
  next_page_token: null,
  page_size: 100,
}

const endpoints = [
  {
    id: 'nep_1',
    name: 'ops-webhook',
    kind: 'webhook',
    display_target: 'https://hooks.acme.io/***',
    status: 'active',
    created_at: NOW,
    updated_at: NOW,
  },
]

const preferences = {
  id: 'np_1',
  delivery_mode: 'in_app_all',
  categories: { system: true, security: true, account: false, agent: false, workflow: false, task: true },
  quiet_hours_enabled: false,
  quiet_hours_start: '22:00',
  quiet_hours_end: '07:00',
  timezone: 'UTC',
  created_at: NOW,
  updated_at: NOW,
}

/** The confirm buttons live in the dialog; row buttons share their labels. */
const modal = (page: Page) => page.locator('.console-modal')

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('a member is invited with the id and role the dialog collected', async ({ page }) => {
  let posted: Record<string, unknown> | null = null

  await page.route('**/api/v1/workspaces/*/members', async (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok({}) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(members) })
  })

  await page.goto('/settings/team', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('wei@acme.io')).toBeVisible()

  await page.getByRole('button', { name: 'Invite member' }).click()
  await expect(page.getByRole('heading', { name: 'Invite member' })).toBeVisible()

  // Create stays disabled until a user id is present.
  const create = modal(page).getByRole('button', { name: 'Create', exact: true })
  await expect(create).toBeDisabled()

  await modal(page).locator('input.input').first().fill('u_9')
  await modal(page).locator('select.input').first().selectOption('Admin')
  await expect(create).toBeEnabled()
  await create.click()

  await expect.poll(() => posted).not.toBeNull()
  // The server's workspace role vocabulary is capitalized (rbac.py).
  expect(posted).toMatchObject({ user_id: 'u_9', role: 'Admin' })
})

test('a member role change PATCHes the membership', async ({ page }) => {
  let patched: Record<string, unknown> | null = null
  let patchedUrl = ''

  await json(page, '**/api/v1/workspaces/*/members', members)
  await page.route('**/api/v1/workspaces/*/members/*', async (route) => {
    patched = route.request().postDataJSON()
    patchedUrl = route.request().url()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok({}) })
  })

  await page.goto('/settings/team', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Change role' }).click()

  // The dialog opens on the member's current role, so Save waits for a change.
  const save = modal(page).getByRole('button', { name: 'Save', exact: true })
  await expect(save).toBeDisabled()
  await modal(page).locator('select.input').first().selectOption('Dev')
  await save.click()

  await expect.poll(() => patched).not.toBeNull()
  expect(patched).toMatchObject({ role: 'Dev' })
  expect(patchedUrl).toContain('/workspaces/workspace-1/members/u_2')
})

test('removing a member deletes the membership after a confirmation', async ({ page }) => {
  let deletedUrl = ''
  let deletedMethod = ''

  await json(page, '**/api/v1/workspaces/*/members', members)
  await page.route('**/api/v1/workspaces/*/members/*', async (route) => {
    deletedUrl = route.request().url()
    deletedMethod = route.request().method()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(null) })
  })

  await page.goto('/settings/team', { waitUntil: 'domcontentloaded' })
  // Only other members carry actions — the server refuses self-removal.
  await expect(page.getByRole('button', { name: 'Remove' })).toHaveCount(1)
  await page.getByRole('button', { name: 'Remove' }).click()

  await expect(page.getByText('Remove Wei from this workspace?')).toBeVisible()
  await modal(page).getByRole('button', { name: 'Remove', exact: true }).click()

  await expect.poll(() => deletedMethod).toBe('DELETE')
  expect(deletedUrl).toContain('/workspaces/workspace-1/members/u_2')
})

test('the password change posts both passwords and nothing else', async ({ page }) => {
  let posted: Record<string, unknown> | null = null

  await page.route('**/api/v1/me/password', async (route) => {
    posted = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(null) })
  })

  await page.goto('/settings/account', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Change password…' }).click()

  const save = modal(page).getByRole('button', { name: 'Save', exact: true })
  const boxes = modal(page).locator('input.input')
  await boxes.nth(0).fill('old-secret')
  await boxes.nth(1).fill('new-secret')
  // A mismatched confirmation cannot be submitted.
  await boxes.nth(2).fill('new-secre')
  await expect(save).toBeDisabled()
  await expect(page.getByText('The two new passwords do not match.')).toBeVisible()

  await boxes.nth(2).fill('new-secret')
  await expect(save).toBeEnabled()
  await save.click()

  await expect.poll(() => posted).not.toBeNull()
  expect(posted).toEqual({ current_password: 'old-secret', new_password: 'new-secret' })
})

test('creating an API key sends the scope and lifetime, and reveals the secret once', async ({ page }) => {
  let posted: Record<string, unknown> | null = null
  const SECRET = 'sk_fixture_created_once'

  await page.route('**/api/v1/api-keys**', async (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({ api_key: SECRET, item: { ...apiKeys.items[0], id: 'key_2', name: 'deploy-bot' } }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(apiKeys) })
  })

  await page.goto('/settings/api', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('ci-pipeline')).toBeVisible()

  await page.getByRole('button', { name: 'Create key' }).click()
  const create = modal(page).getByRole('button', { name: 'Create', exact: true })
  await expect(create).toBeDisabled()

  await modal(page).locator('input.input').first().fill('deploy-bot')
  const selects = modal(page).locator('select.input')
  await selects.nth(0).selectOption('write')
  await selects.nth(1).selectOption('30')
  await create.click()

  await expect.poll(() => posted).not.toBeNull()
  expect(posted).toEqual({ name: 'deploy-bot', scopes: ['write'], expires_in_days: 30 })

  // The plaintext key is shown here and only here.
  await expect(page.getByRole('heading', { name: 'Copy your key now' })).toBeVisible()
  const revealed = page.getByTestId('revealed-api-key')
  await expect(revealed).toHaveValue(SECRET)
  await expect(modal(page).getByRole('button', { name: 'Copy', exact: true })).toBeVisible()

  await modal(page).getByRole('button', { name: 'Done', exact: true }).click()

  // Once dismissed it is gone: not in a dialog, not in the table, nowhere.
  await expect(page.getByTestId('revealed-api-key')).toHaveCount(0)
  await expect(page.locator('.console-modal')).toHaveCount(0)
  expect(await page.content()).not.toContain(SECRET)
  // The table only ever knew the prefix.
  await expect(page.getByText('sk_fixture_a…')).toBeVisible()
})

test('rotating a key posts to the rotate endpoint and reveals the new secret once', async ({ page }) => {
  let rotatedUrl = ''
  const SECRET = 'sk_fixture_rotated_once'

  // The rotate route is registered last so it wins over the list route.
  await json(page, '**/api/v1/api-keys**', apiKeys)
  await page.route('**/api/v1/api-keys/*/rotate', async (route) => {
    rotatedUrl = route.request().url()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ api_key: SECRET, item: apiKeys.items[0] }),
    })
  })

  await page.goto('/settings/api', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Rotate' }).click()

  await expect(page.getByText('Rotate ci-pipeline?')).toBeVisible()
  await modal(page).getByRole('button', { name: 'Rotate', exact: true }).click()

  await expect.poll(() => rotatedUrl).toContain('/api-keys/key_1/rotate')
  await expect(page.getByTestId('revealed-api-key')).toHaveValue(SECRET)

  await modal(page).getByRole('button', { name: 'Done', exact: true }).click()
  await expect(page.getByTestId('revealed-api-key')).toHaveCount(0)
  expect(await page.content()).not.toContain(SECRET)
})

test('notification endpoints can be created, edited, tested and deleted', async ({ page }) => {
  let created: Record<string, unknown> | null = null
  let patched: Record<string, unknown> | null = null
  let deletedMethod = ''
  let testedUrl = ''

  await json(page, '**/api/v1/notifications/preferences', preferences)
  await page.route('**/api/v1/notifications/endpoints', async (route) => {
    if (route.request().method() === 'POST') {
      created = route.request().postDataJSON()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({ ...endpoints[0], id: 'nep_2', name: 'pager', kind: 'slack' }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(endpoints) })
  })
  await page.route('**/api/v1/notifications/endpoints/*', async (route) => {
    const method = route.request().method()
    if (method === 'PATCH') {
      patched = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(endpoints[0]) })
    }
    deletedMethod = method
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(null) })
  })
  // Registered last so it wins over the endpoint-id route above.
  await page.route('**/api/v1/notifications/endpoints/*/test', async (route) => {
    testedUrl = route.request().url()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        id: 'nd_1',
        notification_id: 'n_1',
        endpoint_id: 'nep_1',
        status: 'queued',
        attempt_count: 0,
        available_at: NOW,
        created_at: NOW,
        updated_at: NOW,
      }),
    })
  })

  await page.goto('/settings/notifications', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('ops-webhook')).toBeVisible()

  // Create.
  await page.getByRole('button', { name: 'Add endpoint' }).click()
  const create = modal(page).getByRole('button', { name: 'Create', exact: true })
  await expect(create).toBeDisabled()
  await modal(page).locator('input.input').nth(0).fill('pager')
  await modal(page).locator('select.input').first().selectOption('slack')
  await modal(page).locator('input.input').nth(1).fill('https://hooks.slack.test/T000/B000')
  await create.click()

  await expect.poll(() => created).not.toBeNull()
  expect(created).toEqual({
    name: 'pager',
    kind: 'slack',
    url: 'https://hooks.slack.test/T000/B000',
  })

  // Edit: an empty target box must not blank the stored destination.
  await page.getByRole('button', { name: 'Edit' }).click()
  await modal(page).locator('input.input').nth(0).fill('ops-webhook-2')
  await modal(page).locator('select.input').nth(1).selectOption('disabled')
  await modal(page).getByRole('button', { name: 'Save', exact: true }).click()

  await expect.poll(() => patched).not.toBeNull()
  expect(patched).toMatchObject({ name: 'ops-webhook-2', kind: 'webhook', status: 'disabled' })
  expect(patched && 'url' in patched).toBe(false)

  // Test.
  await page.getByRole('button', { name: 'Test' }).click()
  await expect.poll(() => testedUrl).toContain('/notifications/endpoints/nep_1/test')

  // Delete.
  await page.getByRole('button', { name: 'Delete', exact: true }).first().click()
  await expect(page.getByText('Delete ops-webhook?')).toBeVisible()
  await modal(page).getByRole('button', { name: 'Delete', exact: true }).click()
  await expect.poll(() => deletedMethod).toBe('DELETE')
})

test('the security pane lists sessions and ends the ones that are not this device', async ({
  page,
}) => {
  await json(page, '**/api/v1/me/sessions', [
    {
      id: 'ses_here',
      workspace_id: 'workspace-1',
      status: 'active',
      user_agent: 'Chrome on macOS',
      ip_address: '203.0.113.9',
      created_at: NOW,
      last_seen_at: NOW,
      expires_at: NOW,
      current: true,
    },
    {
      id: 'ses_phone',
      workspace_id: 'workspace-1',
      status: 'active',
      user_agent: 'Safari on iOS',
      ip_address: '198.51.100.4',
      created_at: NOW,
      last_seen_at: NOW,
      expires_at: NOW,
      current: false,
    },
  ])

  const revoked: string[] = []
  await page.route('**/api/v1/me/sessions/ses_phone', (route) => {
    revoked.push(route.request().method())
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ id: 'ses_phone', status: 'revoked', current: false }),
    })
  })

  await page.goto('/settings/security', { waitUntil: 'domcontentloaded' })

  // The current device is named as such and offers no End button: a person
  // ending their own session from this table would be signing themselves out
  // with no way back to it.
  const here = page.locator('tr', { hasText: 'Chrome on macOS' })
  await expect(here).toContainText('this device')
  await expect(here.getByRole('button', { name: 'End' })).toHaveCount(0)

  await page.locator('tr', { hasText: 'Safari on iOS' }).getByRole('button', { name: 'End' }).click()

  await expect.poll(() => revoked).toEqual(['DELETE'])
})

test('signing out everywhere keeps the calling device signed in', async ({ page }) => {
  await json(page, '**/api/v1/me/sessions', [])

  let keepCurrent: string | null = null
  await page.route('**/api/v1/me/sessions/revoke-all**', (route) => {
    keepCurrent = new URL(route.request().url()).searchParams.get('keep_current')
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ revoked: 2 }),
    })
  })

  await page.goto('/settings/security', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Sign out other sessions' }).click()

  await expect.poll(() => keepCurrent).toBe('true')
})

test('two-factor enrolment shows the secret, then the recovery codes once', async ({ page }) => {
  await json(page, '**/api/v1/me/mfa', { enabled: false, pending: false, recovery_codes_remaining: 0 })
  await json(page, '**/api/v1/me/mfa/setup', {
    secret: 'JBSWY3DPEHPK3PXP',
    provisioning_uri: 'otpauth://totp/SOIT%3Ajude%40acme.io?secret=JBSWY3DPEHPK3PXP&issuer=SOIT',
  })

  let confirmedCode: string | null = null
  await page.route('**/api/v1/me/mfa/confirm', async (route) => {
    confirmedCode = JSON.parse(route.request().postData() || '{}').code
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ recovery_codes: ['AAAA-BBBB', 'CCCC-DDDD'] }),
    })
  })

  await page.goto('/settings/account', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Turn on…' }).click()

  // The secret in text, because not every authenticator scans.
  const setup = page.locator('.console-modal').filter({ hasText: 'Set up two-factor' })
  await expect(setup).toContainText('JBSWY3DPEHPK3PXP')
  await page.locator('#mfa-code').fill('123456')
  await page.getByRole('button', { name: 'Turn on', exact: true }).click()

  await expect.poll(() => confirmedCode).toBe('123456')
  // Recovery codes are shown once; they are stored as hashes.
  const recovery = page.locator('.console-modal').filter({ hasText: 'Save your recovery codes' })
  await expect(recovery).toContainText('AAAA-BBBB')
  await expect(recovery).toContainText('CCCC-DDDD')
})

test('turning two-factor off asks for the password, not just a click', async ({ page }) => {
  await json(page, '**/api/v1/me/mfa', {
    enabled: true,
    pending: false,
    recovery_codes_remaining: 8,
  })

  let sentPassword: string | null = null
  await page.route('**/api/v1/me/mfa/disable', async (route) => {
    sentPassword = JSON.parse(route.request().postData() || '{}').password
    return route.fulfill({ status: 204, body: '' })
  })

  await page.goto('/settings/account', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.frow', { hasText: 'Two-factor auth' })).toContainText(
    '8 recovery codes left',
  )

  await page.getByRole('button', { name: 'Turn off…' }).click()
  await page.locator('#mfa-off-password').fill('hunter2')
  await page.getByRole('button', { name: 'Turn it off', exact: true }).click()

  await expect.poll(() => sentPassword).toBe('hunter2')
})

test('the workspace two-factor policy offers only what the server can enforce', async ({
  page,
}) => {
  // One handler for both methods: registering a second route on the same
  // pattern would shadow the first, and the page needs the read to succeed
  // before the control is enabled.
  let patched: unknown = null
  let requireMfa = false
  await page.route('**/api/v1/workspaces/workspace-1', async (route) => {
    if (route.request().method() === 'PATCH') {
      patched = JSON.parse(route.request().postData() || '{}')
      requireMfa = Boolean((patched as { require_mfa?: boolean }).require_mfa)
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        id: 'workspace-1',
        tenant_id: 'tenant-1',
        name: 'acme-robotics',
        require_mfa: requireMfa,
        created_at: NOW,
      }),
    })
  })

  await page.goto('/settings/security', { waitUntil: 'domcontentloaded' })

  // Two states, because that is what the server enforces. A per-role option
  // would be a control that quietly does nothing.
  const policy = page.locator('.frow', { hasText: 'Two-factor policy' }).locator('select')
  await expect(policy.locator('option')).toHaveCount(2)

  await policy.selectOption('required')
  await expect.poll(() => patched).toEqual({ require_mfa: true })
})

test('closing an account is a request with a pause, not a delete button', async ({ page }) => {
  let pending: unknown = null
  let requested: unknown = null
  await page.route('**/api/v1/me/deletion-request', async (route) => {
    const method = route.request().method()
    if (method === 'POST') {
      requested = JSON.parse(route.request().postData() || '{}')
      pending = {
        id: 'adr_1',
        status: 'pending',
        reason: (requested as { reason?: string }).reason ?? null,
        requested_at: NOW,
        execute_after: '2026-09-06T13:00:00Z',
      }
    }
    if (method === 'DELETE') {
      pending = null
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok(pending),
    })
  })

  await page.goto('/settings/account', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Request deletion…' }).click()
  await page.locator('#closure-reason').fill('moving on')
  await page.getByRole('button', { name: 'Request closure' }).click()

  await expect.poll(() => requested).toEqual({ reason: 'moving on' })
  // Nothing is gone: the row now says when it takes effect and offers a way back.
  const row = page.locator('.frow', { hasText: 'Delete account' })
  await expect(row).toContainText('unless you withdraw it')
  await row.getByRole('button', { name: 'Keep my account' }).click()
  await expect(row.getByRole('button', { name: 'Request deletion…' })).toBeVisible()
})

test('members are invited by email where the deployment can send mail', async ({ page }) => {
  await json(page, '**/api/v1/auth/capabilities', { mail_enabled: true })
  await json(page, '**/api/v1/workspaces/workspace-1/invitations', [])

  let invited: unknown = null
  await page.route('**/api/v1/workspaces/workspace-1/invitations', async (route) => {
    if (route.request().method() === 'POST') {
      invited = JSON.parse(route.request().postData() || '{}')
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({
          id: 'inv_1',
          workspace_id: 'workspace-1',
          email: (invited as { email: string }).email,
          role: 'Dev',
          status: 'pending',
          expires_at: '2026-09-13T13:00:00Z',
          created_at: NOW,
        }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok([]) })
  })

  await page.goto('/settings/team', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Invite member' }).click()
  await page.locator('#invite-email').fill('new.person@acme.io')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect.poll(() => invited).toEqual({ email: 'new.person@acme.io', role: 'Dev' })
})

test('a deployment with no mail outlet still adds an existing account by id', async ({
  page,
}) => {
  await json(page, '**/api/v1/auth/capabilities', { mail_enabled: false })

  let added: unknown = null
  await page.route('**/api/v1/workspaces/workspace-1/members', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    added = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ workspace_id: 'workspace-1', user_id: 'u_9', role: 'Dev', created_at: NOW }),
    })
  })

  await page.goto('/settings/team', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Invite member' }).click()

  // No email field: inviting an address needs a mail outlet, and offering it
  // would be a form whose message nothing sends.
  await expect(page.locator('#invite-email')).toHaveCount(0)
  await expect(page.locator('.console-modal')).toContainText('must already belong')
})

/** A dialog row by its label; the input, list box or select beside it. */
const field = (page: Page, label: string) =>
  modal(page).locator('.mrow', { hasText: label }).locator('input, textarea, select')

test('a new key carries the limits the dialog collected and nothing it left empty', async ({
  page,
}) => {
  let posted: Record<string, unknown> | null = null
  await page.route('**/api/v1/api-keys**', async (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({
          api_key: 'sk_fixture_limited',
          item: { ...apiKeys.items[0], id: 'key_3', name: 'partner' },
        }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(apiKeys) })
  })

  await page.goto('/settings/api', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Create key' }).click()
  const create = modal(page).getByRole('button', { name: 'Create', exact: true })

  await modal(page).locator('input.input').first().fill('partner')
  await field(page, 'Calls per minute').fill('60')
  // A count that is not a whole number holds the dialog instead of a 422.
  await field(page, 'Tokens per day').fill('ten')
  await expect(create).toBeDisabled()
  await field(page, 'Tokens per day').fill('200,000')
  await field(page, 'Allowed addresses').fill('203.0.113.7\n198.51.100.0/24')
  await field(page, 'Allowed models').fill('model:openai:gpt-5.5, vmodel:support')
  await field(page, 'Run content').selectOption('metadata_only')
  await create.click()

  await expect.poll(() => posted).not.toBeNull()
  expect(posted).toEqual({
    name: 'partner',
    scopes: ['read'],
    expires_in_days: 90,
    rate_limit_per_minute: 60,
    daily_token_quota: 200000,
    ip_allowlist: ['203.0.113.7', '198.51.100.0/24'],
    allowed_models: ['model:openai:gpt-5.5', 'vmodel:support'],
    content_capture: 'metadata_only',
  })
})

test('editing the limits of a key sends every limit, clearing the ones emptied', async ({
  page,
}) => {
  let patched: Record<string, unknown> | null = null
  let patchedUrl = ''
  const limited = {
    ...apiKeys.items[0],
    rate_limit_per_minute: 30,
    daily_request_quota: null,
    daily_token_quota: null,
    ip_allowlist: ['203.0.113.7/32'],
    allowed_models: null,
    content_capture: null,
  }
  await page.route('**/api/v1/api-keys**', async (route) => {
    if (route.request().method() === 'PATCH') {
      patched = route.request().postDataJSON()
      patchedUrl = route.request().url()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({ ...limited, ...patched }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...apiKeys, items: [limited] }),
    })
  })

  await page.goto('/settings/api', { waitUntil: 'domcontentloaded' })
  // The table says what bounds each key.
  await expect(page.getByText('30/min · addresses: 1')).toBeVisible()

  await page.getByRole('button', { name: 'Limits', exact: true }).click()
  await expect(field(page, 'Calls per minute')).toHaveValue('30')
  await expect(field(page, 'Allowed addresses')).toHaveValue('203.0.113.7/32')
  await field(page, 'Calls per minute').fill('')
  await field(page, 'Calls per 24 hours').fill('5000')
  await modal(page).getByRole('button', { name: 'Save', exact: true }).click()

  await expect.poll(() => patched).not.toBeNull()
  expect(patchedUrl).toContain('/api-keys/key_1')
  expect(patched).toEqual({
    rate_limit_per_minute: null,
    daily_request_quota: 5000,
    daily_token_quota: null,
    ip_allowlist: ['203.0.113.7/32'],
    allowed_models: null,
    content_capture: null,
  })
})

test('a service principal is created with a role and issued a key of its own', async ({
  page,
}) => {
  let createdPrincipal: Record<string, unknown> | null = null
  let postedKey: Record<string, unknown> | null = null
  const principal = {
    id: 'sp_1',
    tenant_id: 't1',
    workspace_id: 'workspace-1',
    name: 'etl-pipeline',
    description: null,
    owner_user_id: 'user-1',
    workspace_role: 'Viewer',
    status: 'active',
    created_by: 'user-1',
    created_at: NOW,
    updated_at: NOW,
  }
  const principals: unknown[] = []

  await json(page, '**/api/v1/workspaces/*/members', members)
  await page.route('**/api/v1/service-principals**', async (route) => {
    if (route.request().method() === 'POST') {
      createdPrincipal = route.request().postDataJSON()
      principals.push(principal)
      return route.fulfill({ status: 201, contentType: 'application/json', body: ok(principal) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(principals) })
  })
  await page.route('**/api/v1/api-keys**', async (route) => {
    if (route.request().method() === 'POST') {
      postedKey = route.request().postDataJSON()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({
          api_key: 'sk_fixture_principal',
          item: { ...apiKeys.items[0], id: 'key_4', name: 'etl-pipeline', principal_id: 'sp_1' },
        }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(apiKeys) })
  })

  await page.goto('/settings/api', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('No service principals.', { exact: false })).toBeVisible()

  await page.getByRole('button', { name: 'New principal' }).click()
  await modal(page).locator('input.input').first().fill('etl-pipeline')
  await field(page, 'Role').selectOption('Viewer')
  await modal(page).getByRole('button', { name: 'Create', exact: true }).click()

  await expect.poll(() => createdPrincipal).toEqual({
    name: 'etl-pipeline',
    workspace_role: 'Viewer',
  })
  const row = page.locator('tr', { hasText: 'etl-pipeline' })
  await expect(row).toContainText('Jude')

  // Issuing from the row of the principal selects it as the holder of the key.
  await row.getByRole('button', { name: 'Issue key' }).click()
  await expect(field(page, 'Issued to')).toHaveValue('sp_1')
  await modal(page).getByRole('button', { name: 'Create', exact: true }).click()

  await expect.poll(() => postedKey).not.toBeNull()
  expect(postedKey).toMatchObject({ name: 'etl-pipeline', principal_id: 'sp_1' })
})

test('a workspace can stop recording run content', async ({ page }) => {
  let patched: unknown = null
  let capture = 'full'
  await page.route('**/api/v1/workspaces/workspace-1', async (route) => {
    if (route.request().method() === 'PATCH') {
      patched = JSON.parse(route.request().postData() || '{}')
      capture = (patched as { content_capture: string }).content_capture
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        id: 'workspace-1',
        tenant_id: 'tenant-1',
        name: 'acme-robotics',
        require_mfa: false,
        content_capture: capture,
        created_at: NOW,
      }),
    })
  })

  await page.goto('/settings/security', { waitUntil: 'domcontentloaded' })
  const select = page.locator('.frow', { hasText: 'Run content' }).locator('select')
  await expect(select).toHaveValue('full')

  await select.selectOption('metadata_only')
  await expect.poll(() => patched).toEqual({ content_capture: 'metadata_only' })
  await expect(select).toHaveValue('metadata_only')
})

test('team channels receive the alerts they subscribe to and are managed by admins', async ({
  page,
}) => {
  const channel = {
    id: 'nep_team',
    name: 'ops-alerts',
    kind: 'slack',
    display_target: 'slack://***',
    status: 'active',
    scope: 'workspace',
    categories: ['alert', 'task'],
    created_at: NOW,
    updated_at: NOW,
  }
  const writes: { method: string; url: string; body: unknown }[] = []
  const saved: { preferences: { categories: Record<string, boolean> } | null } = {
    preferences: null,
  }

  await page.route('**/api/v1/notifications/preferences', async (route) => {
    if (route.request().method() === 'PUT') saved.preferences = route.request().postDataJSON()
    // A preference stored before alerts existed has no "alert" key at all.
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(preferences) })
  })
  await json(page, '**/api/v1/notifications/endpoints', [])
  await page.route('**/api/v1/notifications/workspace-endpoints**', async (route) => {
    const request = route.request()
    if (request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok([channel]) })
    }
    writes.push({ method: request.method(), url: request.url(), body: request.postDataJSON() })
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(channel) })
  })

  await page.goto('/settings/notifications', { waitUntil: 'domcontentloaded' })
  const row = page.locator('tr', { hasText: 'ops-alerts' })
  await expect(row).toContainText('budgets & credit')
  await expect(row).toContainText('failed runs')

  // Alerts are on unless switched off, as the server treats a missing category.
  const alerts = page.locator('.frow', { hasText: 'Budget and credit alerts' }).locator('input')
  await expect(alerts).toBeChecked()
  // Controlled by the stored preference, so the box follows the server, not the click.
  await alerts.click()
  await expect.poll(() => saved.preferences?.categories.alert).toBe(false)

  await row.getByRole('button', { name: 'Test' }).click()
  await expect.poll(() => writes.map((write) => write.url)).toContainEqual(
    expect.stringContaining('/workspace-endpoints/nep_team/test'),
  )

  await page.getByRole('button', { name: 'Add channel' }).click()
  const create = modal(page).getByRole('button', { name: 'Create', exact: true })
  await modal(page).locator('.mrow', { hasText: /^Name/ }).locator('input').fill('on-call')
  await modal(page).locator('.mrow', { hasText: /^Target/ }).locator('input').fill('https://hooks.acme.io/oncall')
  await modal(page).getByLabel('budgets & credit').uncheck()
  // A channel must receive something.
  await expect(create).toBeDisabled()
  await modal(page).getByLabel('failed runs').check()
  await create.click()

  await expect.poll(() => writes.filter((write) => write.method === 'POST').length).toBe(2)
  const posted = writes.filter((write) => write.method === 'POST')[1]
  expect(posted.url).toMatch(/\/workspace-endpoints$/)
  expect(posted.body).toEqual({
    name: 'on-call',
    kind: 'slack',
    url: 'https://hooks.acme.io/oncall',
    categories: ['task'],
  })
})

test('members who cannot manage team channels are told why', async ({ page }) => {
  await json(page, '**/api/v1/notifications/preferences', preferences)
  await json(page, '**/api/v1/notifications/endpoints', [])
  await page.route('**/api/v1/notifications/workspace-endpoints**', (route) =>
    route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'FORBIDDEN', message: 'Forbidden' }),
    }),
  )

  await page.goto('/settings/notifications', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Workspace owners and admins manage team channels.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add channel' })).toHaveCount(0)
})

test('personal data handling is set per direction and can follow the deployment again', async ({
  page,
}) => {
  const patches: unknown[] = []
  let workspace: Record<string, unknown> = {
    id: 'workspace-1',
    tenant_id: 'tenant-1',
    name: 'acme-robotics',
    require_mfa: false,
    content_capture: 'full',
    pii_action_inbound: null,
    pii_action_outbound: null,
    pii_action_default: 'observe',
    created_at: NOW,
  }
  await page.route('**/api/v1/workspaces/workspace-1', async (route) => {
    if (route.request().method() === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}')
      patches.push(body)
      workspace = { ...workspace, ...body }
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(workspace) })
  })

  await page.goto('/settings/security', { waitUntil: 'domcontentloaded' })
  const inbound = page.getByLabel('Personal data in prompts')
  await expect(inbound).toHaveValue('')
  await expect(inbound.locator('option').first()).toHaveText('deployment default (observe)')

  await inbound.selectOption('block')
  await expect.poll(() => patches).toEqual([{ pii_action_inbound: 'block' }])
  await expect(inbound).toHaveValue('block')

  // Back to the deployment is an explicit null, not an omitted field.
  await inbound.selectOption('')
  await expect.poll(() => patches.length).toBe(2)
  expect(patches[1]).toEqual({ pii_action_inbound: null })
  await expect(page.getByLabel('Personal data in answers')).toHaveValue('')
})
