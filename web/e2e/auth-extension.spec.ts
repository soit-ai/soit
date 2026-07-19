import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const appRoot = path.resolve(process.cwd(), 'app')

test('community sign-in route uses the auth extension boundary', () => {
  const source = fs.readFileSync(path.join(appRoot, 'routes/auth/sign-in.tsx'), 'utf-8')

  expect(source).toContain("@/extensions/auth")
  expect(source).not.toContain("@/routes/auth/ui/login-form")
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
