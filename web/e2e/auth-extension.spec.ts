import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { mockShellApi } from './helpers'

const appRoot = path.resolve(process.cwd(), 'app')

test('community sign-in route uses the auth extension boundary', () => {
  const source = fs.readFileSync(path.join(appRoot, 'auth/sign-in.tsx'), 'utf-8')

  expect(source).toContain("@/extensions/auth")
  expect(source).not.toContain("@/auth/ui/login-form")
  expect(source).not.toContain("better-auth")
  expect(source).not.toContain("soit-enterprise")
})

test('community auth extension defaults to the existing login form without enterprise imports', () => {
  const extensionSource = fs.readFileSync(path.join(appRoot, 'extensions/auth/index.ts'), 'utf-8')

  expect(extensionSource).toContain("community-auth-panel")
  expect(extensionSource).not.toContain("better-auth")
  expect(extensionSource).not.toContain("soit-enterprise")
})

test('sign-in renders inside the application query client', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())

  await page.goto('/sign-in', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Sign in to SOIT' })).toBeVisible()
  await expect(page.getByLabel('Email')).toBeVisible()
  await expect(page.getByText('No QueryClient set')).toHaveCount(0)
})

test('community sign-in does not advertise unavailable identity or legal flows', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  // A deployment with no mail outlet cannot send a reset link, so it must not
  // offer one. This is the same rule as before; what changed is that the
  // answer now comes from the server rather than being fixed.
  await page.route('**/api/v1/auth/capabilities', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { mail_enabled: false },
      }),
    }),
  )
  await page.goto('/sign-in', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('button', { name: 'Apple' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Google' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: /forgot your password/i })).toHaveCount(0)
  await expect(page.locator('a[href="#"]')).toHaveCount(0)
})

test('sign-in offers a reset only where the deployment can send mail', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  await page.route('**/api/v1/auth/capabilities', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { mail_enabled: true },
      }),
    }),
  )

  await page.goto('/sign-in', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('link', { name: /forgot your password/i })).toBeVisible()
})

test('the reset page answers the same way whether or not the address is known', async ({
  page,
}) => {
  await page.addInitScript(() => localStorage.clear())
  await page.route('**/api/v1/auth/capabilities', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { mail_enabled: true },
      }),
    }),
  )
  await page.route('**/api/v1/auth/password-reset', (route) =>
    route.fulfill({ status: 204, body: '' }),
  )

  await page.goto('/forgot-password', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill('nobody@example.com')
  await page.getByRole('button', { name: 'Send reset link' }).click()

  // No confirmation that the address exists — that would make this form a way
  // to find out who has an account.
  await expect(page.getByRole('heading', { name: 'If that address has an account' })).toBeVisible()
})

test('a reset page with no mail outlet says so instead of collecting an address', async ({
  page,
}) => {
  await page.addInitScript(() => localStorage.clear())
  await page.route('**/api/v1/auth/capabilities', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { mail_enabled: false },
      }),
    }),
  )

  await page.goto('/forgot-password', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('no mail outlet configured')).toBeVisible()
  await expect(page.getByLabel('Email')).toHaveCount(0)
})

const capabilities = (page: import('@playwright/test').Page, data: Record<string, unknown>) =>
  page.route('**/api/v1/auth/capabilities', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data }),
    }),
  )

test('sign-up names an organization only when it founds one', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  await capabilities(page, {
    mail_enabled: false,
    public_registration: true,
    sign_up_founds_organization: true,
  })
  await page.goto('/sign-up', { waitUntil: 'domcontentloaded' })
  await expect(page.getByLabel('Organisation')).toBeVisible()

  // Once a single-organization deployment has its organization, a sign-up
  // joins it, so there is nothing to name.
  await page.unroute('**/api/v1/auth/capabilities')
  await capabilities(page, {
    mail_enabled: false,
    public_registration: true,
    sign_up_founds_organization: false,
  })
  await page.goto('/sign-up', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Join your team')).toBeVisible()
  await expect(page.getByLabel('Organisation')).toHaveCount(0)
})

test('sign-up with public registration off asks for an invitation', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  await capabilities(page, {
    mail_enabled: true,
    public_registration: false,
    sign_up_founds_organization: false,
  })

  await page.goto('/sign-up', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Sign-up needs an invitation' })).toBeVisible()
  await expect(page.getByLabel('Email')).toHaveCount(0)
})

test('signing up from an invitation link redeems it', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  await capabilities(page, {
    mail_enabled: true,
    public_registration: false,
    sign_up_founds_organization: false,
  })
  let body: Record<string, unknown> | null = null
  await page.route('**/api/v1/register**', async (route) => {
    body = route.request().postDataJSON()
    await route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({
      success: false, code: 'VALIDATION_ERROR', message: 'That invitation has expired',
    }) })
  })

  await page.goto('/sign-up?invitation=tok-123', { waitUntil: 'domcontentloaded' })
  // An invitation admits even with public registration off.
  await expect(page.getByText('Invitation', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Organisation')).toHaveCount(0)
  await page.getByLabel('Email').fill('newcomer@example.com')
  await page.getByLabel('Your name').fill('Newcomer')
  await page.getByLabel('Password', { exact: true }).fill('password123')
  await page.getByLabel('Confirm Password').fill('password123')
  await page.getByRole('button', { name: 'Create workspace' }).click()

  await expect(page.getByText('Use the address the invitation was sent to')).toBeVisible()
  expect(body).toMatchObject({ email: 'newcomer@example.com', invitation_token: 'tok-123' })
  // A refused invitation is not a lost session: the page stays put.
  await expect(page).toHaveURL(/\/sign-up\?invitation=tok-123$/)
})

test('an invitation link offers a signed-out visitor both ways in', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())

  await page.goto('/accept-invitation?token=tok-123', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Join a workspace' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Sign in to accept' })).toHaveAttribute(
    'href',
    '/sign-in?redirect=%2Faccept-invitation%3Ftoken%3Dtok-123',
  )
  await expect(page.getByRole('link', { name: 'Create one' })).toHaveAttribute(
    'href',
    '/sign-up?invitation=tok-123',
  )
})

test('accepting an invitation switches to the invited workspace', async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('token')) localStorage.setItem('token', 'e2e-token')
    if (!localStorage.getItem('workspace_id')) localStorage.setItem('workspace_id', 'workspace-1')
  })
  await mockShellApi(page)
  let accepted: Record<string, unknown> | null = null
  await page.route('**/api/v1/invitations/accept', async (route) => {
    accepted = route.request().postDataJSON()
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      success: true, code: 'OK', message: 'OK', data: {
        id: 'inv-1', workspace_id: 'workspace-9', email: 'user@example.com', role: 'Dev',
        status: 'accepted', expires_at: '2026-12-01T00:00:00Z', created_at: '2026-11-26T00:00:00Z',
      },
    }) })
  })

  await page.goto('/accept-invitation?token=tok-123', { waitUntil: 'domcontentloaded' })
  // Opening the link changes nothing by itself; accepting takes a click.
  expect(accepted).toBeNull()
  await page.getByRole('button', { name: 'Accept invitation' }).click()

  await expect.poll(() => page.evaluate(() => localStorage.getItem('workspace_id'))).toBe(
    'workspace-9',
  )
  expect(accepted).toEqual({ token: 'tok-123' })
})

test('an invitation for another address says so and keeps the session', async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('token')) localStorage.setItem('token', 'e2e-token')
  })
  await mockShellApi(page)
  await page.route('**/api/v1/invitations/accept', (route) =>
    route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({
      success: false, code: 'FORBIDDEN', message: 'This invitation was sent to a different address',
    }) }),
  )

  await page.goto('/accept-invitation?token=tok-123', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Accept invitation' }).click()

  await expect(page.getByText('sent to a different address')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign in as someone else' })).toBeVisible()
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBe('e2e-token')
})

test('protected routes redirect unauthenticated users with a local return target', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  await page.goto('/build/knowledge?view=library', { waitUntil: 'domcontentloaded' })

  await expect(page).toHaveURL(/\/sign-in\?redirect=%2Fbuild%2Fknowledge%3Fview%3Dlibrary$/)
})

test('sign-in resumes a safe local route and ignores an external redirect', async ({
  page,
  baseURL,
}) => {
  await page.addInitScript(() => localStorage.clear())
  await page.route('**/api/v1/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          access_token: 'new-token',
          token_type: 'bearer',
          expires_in: 3600,
          workspace_id: 'workspace-1',
        },
      }),
    })
  })
  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          id: 'user-1', email: 'user@example.com', name: 'User', tenant_id: 'tenant-1', workspace_id: 'workspace-1',
        },
      }),
    })
  })

  await page.goto('/sign-in?redirect=%2Fknowledge%3Fview%3Dlibrary', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill('user@example.com')
  await page.getByLabel('Password').fill('password123')
  await page.getByRole('button', { name: 'Open workspace' }).click()
  await expect(page).toHaveURL(/\/knowledge\?view=library$/)

  await page.evaluate(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('workspace_id')
  })
  await page.goto('/sign-in?redirect=https%3A%2F%2Fevil.example%2Fsteal', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill('user@example.com')
  await page.getByLabel('Password').fill('password123')
  await page.getByRole('button', { name: 'Open workspace' }).click()
  await expect(page).toHaveURL(new RegExp(`^${baseURL?.replace(/\/$/, '')}/$`))
})

test('logout clears authentication, scope, and persisted user state', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('token_typeof', 'string')
    localStorage.setItem('tenant_id', 'tenant-1')
    localStorage.setItem('tenant_id_typeof', 'string')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('workspace_id_typeof', 'string')
    localStorage.setItem('soit-user-store', JSON.stringify({ state: { currentUser: { id: 'stale-user' } }, version: 0 }))
  })
  await mockShellApi(page)

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  // The console shell's only account surface is the rail avatar.
  await page.getByRole('button', { name: 'Account' }).click()
  await page.getByRole('menuitem', { name: 'Log out' }).click()

  await expect(page).toHaveURL(/\/sign-in$/)
  await expect.poll(() => page.evaluate(() => ({
    token: localStorage.getItem('token'),
    tenant: localStorage.getItem('tenant_id'),
    workspace: localStorage.getItem('workspace_id'),
    user: localStorage.getItem('soit-user-store'),
    tokenType: localStorage.getItem('token_typeof'),
  }))).toEqual({ token: null, tenant: null, workspace: null, user: null, tokenType: null })
})

test('an expired access token is renewed once and the request is replayed', async ({ page }) => {
  // The whole point of the refresh flow: an expiry mid-session is not
  // something a person should have to notice.
  await page.addInitScript(() => {
    localStorage.setItem('token', 'expired-token')
    localStorage.setItem('refresh_token', 'refresh-1')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)

  let refreshCalls = 0
  await page.route('**/api/v1/refresh', (route) => {
    refreshCalls += 1
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: {
          access_token: 'fresh-token',
          token_type: 'bearer',
          expires_in: 1800,
          workspace_id: 'workspace-1',
          refresh_token: 'refresh-2',
        },
      }),
    })
  })

  const seenTokens: string[] = []
  await page.route('**/api/v1/agents/workbench**', (route) => {
    const auth = route.request().headers()['authorization'] || ''
    seenTokens.push(auth)
    if (auth.includes('expired-token')) {
      return route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ success: false, code: 'UNAUTHORIZED', message: 'Token has expired' }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: {
          summary: { total_agents: 2, updated_at: '2026-08-29T13:00:00Z' },
          tabs: { all: 2 },
          items: [],
          next_page_token: null,
          page_size: 50,
        },
      }),
    })
  })

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  // The retried call carried the new token, and the rotated refresh token was
  // stored for next time.
  await expect.poll(() => seenTokens.some((value) => value.includes('fresh-token'))).toBe(true)
  await expect.poll(() => refreshCalls).toBeGreaterThan(0)
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('refresh_token')))
    .toBe('refresh-2')
  // Still on the page: a renewed token must not bounce the user to sign-in.
  await expect(page).toHaveURL(/\/build\/agents/)
})

test('a refresh that fails sends the user to sign in rather than looping', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'expired-token')
    localStorage.setItem('refresh_token', 'stale-refresh')
    localStorage.setItem('workspace_id', 'workspace-1')
  })
  await mockShellApi(page)

  let refreshCalls = 0
  await page.route('**/api/v1/refresh', (route) => {
    refreshCalls += 1
    return route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'UNAUTHORIZED', message: 'Session has ended' }),
    })
  })
  await page.route('**/api/v1/agents/workbench**', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'UNAUTHORIZED', message: 'Token has expired' }),
    }),
  )

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  await expect(page).toHaveURL(/\/sign-in/, { timeout: 15000 })
  // One attempt per failing request at most, never a loop against a dead token.
  expect(refreshCalls).toBeLessThan(10)
})
