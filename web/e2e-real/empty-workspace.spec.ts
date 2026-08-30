import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const apiBaseURL = process.env.SOIT_REAL_API_BASE_URL || 'http://127.0.0.1:9200/api/v1'
const webBaseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5000'

type Envelope<T> = {
  success: boolean
  code: string
  message: string
  data: T
}

async function authHeaders(page: Page): Promise<Record<string, string>> {
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

async function postData<T>(
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

test('fresh browser workspace completes real create, publish, execute, and observe paths', async ({
  page,
  request,
}) => {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  const email = `fullstack-${suffix}@example.com`
  const password = 'FullStackRelease123!'

  await page.goto('/knowledge?view=library', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/sign-in\?redirect=/)

  await page.goto('/sign-up', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Your name').fill('Full Stack Release')
  await page.getByLabel('Organisation').fill(`Release ${suffix}`)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm Password').fill(password)
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await expect(page).toHaveURL(new URL('/', webBaseURL).toString())

  const headers = await authHeaders(page)
  const currentUserResponse = await request.get(`${apiBaseURL}/me`, { headers })
  expect(currentUserResponse.ok()).toBe(true)
  const currentUser = (await currentUserResponse.json()) as Envelope<{
    email: string
    workspace_id: string
  }>
  expect(currentUser.data.email).toBe(email)

  // The console creates a knowledge base from its own page, not a dialog: the
  // wizard carries source, chunking and schedule choices the create payload
  // folds into settings_json.
  const knowledgeName = `Release knowledge ${suffix}`
  await page.goto('/build/knowledge/new', { waitUntil: 'domcontentloaded' })
  await page.getByPlaceholder('product-docs').fill(knowledgeName)
  const knowledgeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/knowledge'),
  )
  await page.getByRole('button', { name: 'Create library' }).click()
  const knowledgeResponse = await knowledgeResponsePromise
  expect(knowledgeResponse.status()).toBe(201)
  const knowledge = (await knowledgeResponse.json()) as Envelope<{ id: string; name: string }>
  await expect(page).toHaveURL(new RegExp(`/build/knowledge/${knowledge.data.id}$`))
  await expect(page.getByText(knowledgeName, { exact: true }).first()).toBeVisible()

  const agentName = `Release agent ${suffix}`
  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New agent' }).click()
  const agentModal = page.locator('.console-modal')
  await expect(agentModal.getByRole('heading', { name: 'New agent' })).toBeVisible()
  await agentModal.locator('input.input').first().fill(agentName)
  await agentModal.locator('input.input').nth(1).fill('Real full-stack agent')
  const agentResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/agents'),
  )
  await agentModal.getByRole('button', { name: 'Create' }).click()
  const agentResponse = await agentResponsePromise
  expect(agentResponse.status()).toBe(201)
  const agent = (await agentResponse.json()) as Envelope<{ id: string }>
  await expect(page).toHaveURL(new RegExp(`/build/agents/${agent.data.id}$`))
  await expect(page.getByText(agentName, { exact: true }).first()).toBeVisible()

  const version = await postData<{ id: string }>(
    request,
    `/agents/${agent.data.id}/versions`,
    headers,
    {
      system_prompt: 'Answer using the resources bound to this release candidate.',
      bindings: {
        model_ref: 'model:test:fullstack-release',
        knowledge_refs: [`knowledge:${knowledge.data.id}`],
      },
      verify: false,
    },
  )
  await postData(
    request,
    `/agents/${agent.data.id}/publish`,
    headers,
    { version_id: version.id },
  )
  const agentRun = await postData<{
    run_id: string
    output: string
    thread_id: string
  }>(request, `/agents/${agent.data.id}/execute`, headers, {
    input: 'Prove this request reached the real runtime.',
  })
  expect(agentRun.run_id).toBeTruthy()
  expect(agentRun.output).toBeTruthy()
  expect(agentRun.thread_id).toBeTruthy()

  await page.goto(`/observe/runs/${agentRun.run_id}`, {
    waitUntil: 'domcontentloaded',
  })
  await expect(page.getByText('Step ledger', { exact: true })).toBeVisible()
  await expect(page.getByText('Cost breakdown', { exact: true })).toBeVisible()

  // A workflow starts from a named draft and a template, so the builder opens
  // on a real id rather than on `new`.
  await page.goto('/build/workflows/new', { waitUntil: 'domcontentloaded' })
  await page.getByPlaceholder('my-workflow').fill(`release-flow-${suffix}`)
  const workflowResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/workflows'),
  )
  await page.getByRole('button', { name: 'Use template' }).first().click()
  const workflowResponse = await workflowResponsePromise
  expect(workflowResponse.status()).toBe(201)
  const workflow = (await workflowResponse.json()) as Envelope<{ id: string }>
  await expect(page).toHaveURL(new RegExp(`/build/workflows/${workflow.data.id}$`))
  await expect(page).not.toHaveURL(/\/build\/workflows\/new$/)

  const workflowVersion = await postData<{ id: string }>(
    request,
    `/workflows/${workflow.data.id}/versions`,
    headers,
    {
      graph_json: {
        name: 'fullstack-release-flow',
        inputs_schema: {
          type: 'object',
          properties: { value: { type: 'string' } },
        },
        outputs_schema: {
          type: 'object',
          properties: { value: { type: 'string' } },
        },
        graph: {
          nodes: [
            {
              id: 'set_value',
              type: 'set_var',
              params: { key: 'value', value: '{{ inputs.value }}' },
            },
            {
              id: 'output_value',
              type: 'output',
              params: { value: '{{ steps.set_value.output.value }}' },
            },
          ],
          edges: [
            { id: 'edge-1', from: 'set_value', to: 'output_value' },
          ],
        },
      },
    },
  )
  const preview = await postData<{ output: { value: string } }>(
    request,
    `/workflows/${workflow.data.id}/versions/${workflowVersion.id}/preview`,
    headers,
    { inputs: { value: 'preview-ok' } },
  )
  expect(preview.output).toEqual({ value: 'preview-ok' })
  await postData(
    request,
    `/workflows/${workflow.data.id}/publish`,
    headers,
    { version_id: workflowVersion.id },
  )
  const workflowRun = await postData<{ output: { value: string } }>(
    request,
    `/workflows/${workflow.data.id}/execute`,
    headers,
    { value: 'published-ok' },
  )
  expect(workflowRun.output).toEqual({ value: 'published-ok' })
})
