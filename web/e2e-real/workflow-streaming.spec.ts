import { expect, test } from '@playwright/test'

import { apiBaseURL, authHeaders, getData, postData, signUpFreshWorkspace } from './helpers'

type WorkflowVersion = { id: string }

async function publishTwoNodeWorkflow(
  request: import('@playwright/test').APIRequestContext,
  headers: Record<string, string>,
  suffix: string,
): Promise<string> {
  const workflow = await postData<{ id: string }>(request, '/workflows', headers, {
    name: `E2E workflow ${suffix}`,
    description: 'Real backend workflow',
  })
  const version = await postData<WorkflowVersion>(
    request,
    `/workflows/${workflow.id}/versions`,
    headers,
    {
      graph_json: {
        name: 'e2e-stream-flow',
        inputs_schema: { type: 'object', properties: { value: { type: 'string' } } },
        outputs_schema: { type: 'object', properties: { value: { type: 'string' } } },
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
          edges: [{ id: 'edge-1', from: 'set_value', to: 'output_value' }],
        },
      },
    },
  )
  await postData(request, `/workflows/${workflow.id}/publish`, headers, {
    version_id: version.id,
  })
  return workflow.id
}

/**
 * Workflow execution was moved out of the SSE request so closing the page can
 * no longer abort work that has already caused side effects. Only a live
 * server can show that the stream and the execution are actually separate.
 */
test('streaming a workflow reports compiled, run and complete events', async ({
  page,
  request,
}) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)
  const workflowId = await publishTwoNodeWorkflow(request, headers, suffix)

  const response = await request.post(`${apiBaseURL}/workflows/${workflowId}/stream`, {
    headers: { ...headers, Accept: 'text/event-stream' },
    data: { inputs: { value: 'streamed-ok' } },
  })
  expect(response.ok()).toBeTruthy()
  expect(response.headers()['content-type']).toContain('text/event-stream')

  const body = await response.text()
  expect(body).toContain('event: start')
  expect(body).toContain('event: compiled')
  expect(body).toContain('event: complete')

  const runId = [...body.matchAll(/"run_id":\s*"([^"]+)"/g)].at(0)?.[1]
  expect(runId, 'the stream must name the run it started').toBeTruthy()

  // The run is persisted evidence, not just stream output.
  const detail = await getData<{ run: { id: string; status: string } }>(
    request,
    `/runs/${runId}`,
    headers,
  )
  expect(detail.run.id).toBe(runId)
  expect(detail.run.status).toBe('succeeded')
})

test('a workflow run survives the client that started it disconnecting', async ({
  page,
  request,
}) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)
  const workflowId = await publishTwoNodeWorkflow(request, headers, suffix)

  // Abandon the stream immediately: execution runs on its own session and
  // must not be cancelled when the consumer leaves.
  const controller = new AbortController()
  const pending = fetch(`${apiBaseURL}/workflows/${workflowId}/stream`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ inputs: { value: 'abandoned-ok' } }),
    signal: controller.signal,
  }).catch(() => undefined)
  await page.waitForTimeout(500)
  controller.abort()
  await pending

  await expect
    .poll(
      async () => {
        const runs = await getData<{ items: Array<{ mode: string; status: string }> }>(
          request,
          '/runs?page_size=20',
          headers,
        )
        return runs.items.filter((item) => item.mode === 'workflow')
      },
      { timeout: 30_000, message: 'the abandoned workflow run should still reach a terminal state' },
    )
    .toEqual([expect.objectContaining({ status: 'succeeded' })])
})
