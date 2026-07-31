import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const apiBaseURL =
  process.env.SOIT_REAL_API_BASE_URL || 'http://127.0.0.1:9200/api/v1'
export const webBaseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5000'

export type Envelope<T> = {
  success: boolean
  code: string
  message: string
  data: T
}

/**
 * Read the credentials the browser holds after signing up.
 *
 * The API calls in these specs travel the same authenticated path the UI uses,
 * so a spec cannot pass against a workspace the browser could not reach.
 */
export async function authHeaders(page: Page): Promise<Record<string, string>> {
  const scope = await page.evaluate(() => ({
    token: localStorage.getItem('token'),
    workspaceId: localStorage.getItem('workspace_id'),
  }))
  expect(scope.token).toBeTruthy()
  expect(scope.workspaceId).toBeTruthy()
  return {
    Authorization: `Bearer ${scope.token}`,
    'X-Workspace-Id': String(scope.workspaceId),
  }
}

export async function postData<T>(
  request: APIRequestContext,
  path: string,
  headers: Record<string, string>,
  data: unknown,
): Promise<T> {
  const response = await request.post(`${apiBaseURL}${path}`, { headers, data })
  const body = (await response.json()) as Envelope<T>
  expect(response.ok(), `${path}: ${body.code} ${body.message}`).toBeTruthy()
  expect(body.success).toBe(true)
  return body.data
}

export async function getData<T>(
  request: APIRequestContext,
  path: string,
  headers: Record<string, string>,
): Promise<T> {
  const response = await request.get(`${apiBaseURL}${path}`, { headers })
  const body = (await response.json()) as Envelope<T>
  expect(response.ok(), `${path}: ${body.code} ${body.message}`).toBeTruthy()
  return body.data
}

/**
 * Register a brand new tenant through the sign-up form.
 *
 * Every spec starts from an empty workspace so nothing depends on seed data;
 * a spec that needs fixtures would stop proving the first-run journey works.
 */
export async function signUpFreshWorkspace(page: Page): Promise<{
  suffix: string
  email: string
}> {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  const email = `e2e-${suffix}@example.com`
  const password = 'FullStackRelease123!'

  await page.goto('/sign-up', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Name', { exact: true }).fill('Real Backend E2E')
  await page.getByLabel('Tenant Name (optional)').fill(`E2E ${suffix}`)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm Password').fill(password)
  await page.getByRole('button', { name: 'Sign up' }).click()
  await expect(page).toHaveURL(new URL('/', webBaseURL).toString())

  return { suffix, email }
}

/** Create and publish an agent bound to the deterministic test model. */
export async function publishAgent(
  request: APIRequestContext,
  headers: Record<string, string>,
  suffix: string,
  overrides: { knowledgeRefs?: string[]; toolRefs?: string[] } = {},
): Promise<string> {
  const agent = await postData<{ id: string }>(request, '/agents', headers, {
    name: `E2E agent ${suffix}`,
    description: 'Real backend agent',
    visibility: 'private',
  })
  const bindings: Record<string, unknown> = {
    model_ref: `model:test:e2e-${suffix}`,
  }
  if (overrides.knowledgeRefs) bindings.knowledge_refs = overrides.knowledgeRefs
  if (overrides.toolRefs) bindings.tool_refs = overrides.toolRefs

  const version = await postData<{ id: string }>(
    request,
    `/agents/${agent.id}/versions`,
    headers,
    {
      system_prompt: 'Answer using the bound resources.',
      bindings,
      verify: false,
    },
  )
  await postData(request, `/agents/${agent.id}/publish`, headers, {
    version_id: version.id,
  })
  return agent.id
}
