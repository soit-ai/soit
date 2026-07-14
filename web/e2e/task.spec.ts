import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const taskRows = [
  {
    id: 'task_failed_contract',
    tenant_id: 'tenant-1',
    workspace_id: 'workspace-1',
    display_name: '合同审批流程 - 合同评审',
    task_type: 'wf_step',
    status: 'failed',
    agent_id: 'agt_contract',
    thread_id: 'thread_contract',
    run_id: 'run_contract',
    owner: 'Bob',
    error_code: 'TASK_FAILED',
    error_message: 'contract_id is empty',
    created_at: '2026-06-01T20:20:00.000Z',
    updated_at: '2026-06-01T20:37:56.000Z',
    started_at: '2026-06-01T20:27:42.000Z',
    finished_at: null,
  },
  {
    id: 'task_running_contract',
    tenant_id: 'tenant-1',
    workspace_id: 'workspace-1',
    display_name: '客户画像智能问答更新',
    task_type: 'agent.execute',
    status: 'running',
    agent_id: 'agt_customer',
    thread_id: 'thread_customer',
    run_id: 'run_customer',
    owner: 'Grace',
    error_code: null,
    error_message: null,
    created_at: '2026-06-01T20:18:00.000Z',
    updated_at: '2026-06-01T20:41:23.000Z',
    started_at: '2026-06-01T20:19:00.000Z',
    finished_at: null,
  },
]

const taskWorkbench = {
  summary: {
    total_tasks: 249,
    waiting_approval: 28,
    failed: 73,
    waiting_input: 54,
    long_running: 6,
    running: 386,
    today_created: 128,
    today_completed: 312,
    updated_at: '2026-06-01T20:45:00.000Z',
  },
  tabs: {
    all: 249,
    waiting_approval: 28,
    failed: 73,
    waiting_input: 54,
    long_running: 6,
    running: 386,
  },
  items: taskRows,
  total: 249,
  page_size: 2,
  next_page_token: null,
}

const taskHandling = {
  task: {
    ...taskRows[0],
    input_json: {},
    output_json: {},
    progress_json: { stage: 'failed' },
    created_by: 'Bob',
    updated_by: 'Bob',
  },
  summary: {
    title: '合同审批流程 - 合同评审',
    status: 'failed',
    task_type: 'wf_step',
    error_code: 'TASK_FAILED',
    error_message: 'contract_id is empty',
    updated_at: '2026-06-01T20:37:56.000Z',
  },
  runtime_context: {
    agent_id: 'agt_contract',
    thread_id: 'thread_contract',
    run_id: 'run_contract',
  },
  available_actions: ['retry'],
  events: [
    {
      id: 'event_failed',
      tenant_id: 'tenant-1',
      workspace_id: 'workspace-1',
      task_id: 'task_failed_contract',
      event_type: 'task.failed',
      payload_json: { message: 'contract_id is empty' },
      created_at: '2026-06-01T20:27:56.000Z',
    },
  ],
  checkpoints: [
    {
      id: 'checkpoint_failed',
      tenant_id: 'tenant-1',
      workspace_id: 'workspace-1',
      task_id: 'task_failed_contract',
      checkpoint_no: 1,
      status: 'failed',
      payload_json: { node: '合同评审' },
      created_at: '2026-06-01T20:27:55.000Z',
    },
  ],
}

async function mockTaskApi(page: Page) {
  let retryCalls = 0

  await page.route('**/api/v1/tasks**', async (route) => {
    const method = route.request().method()
    const url = new URL(route.request().url())

    if (method === 'GET' && url.pathname.endsWith('/api/v1/tasks/workbench/items')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: taskWorkbench }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/tasks/workbench')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: taskWorkbench }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/tasks/task_failed_contract/handling')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: taskHandling }),
      })
      return
    }

    if (method === 'POST' && url.pathname.endsWith('/api/v1/tasks/task_failed_contract/retry')) {
      retryCalls += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { action: 'retry', task: taskHandling.task } }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: taskRows,
          page_size: 2,
          next_page_token: null,
        },
      }),
    })
  })

  return {
    retryCalls: () => retryCalls,
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
})

test('task center renders workbench data and opens processing page from sidebar', async ({ page }) => {
  await mockTaskApi(page)

  await page.goto('/tasks', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: '任务运行中心' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('button', { name: '全部 249' })).toBeVisible()
  await expect(page.getByRole('table').getByText('合同审批流程 - 合同评审')).toBeVisible()

  await page.getByRole('link', { name: '任务处理' }).click()
  await expect(page).toHaveURL(/\/tasks\/processing/)
  await expect(page.getByRole('heading', { name: '任务处理' })).toBeVisible()
})

test('task processing opens handling sheet from row click and retries selected task', async ({ page }) => {
  const api = await mockTaskApi(page)

  await page.goto('/tasks/processing', { waitUntil: 'domcontentloaded' })
  await page.getByText('合同审批流程 - 合同评审').click()

  await expect(page).toHaveURL(/taskId=task_failed_contract/)
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('heading', { name: '处理面板' })).toBeVisible()
  await expect(page.getByText('contract_id is empty')).toBeVisible()
  await expect(page.getByText('task.failed')).toBeVisible()

  await page.getByRole('button', { name: '重试' }).click()
  await expect.poll(api.retryCalls).toBe(1)
})

test('task processing opens handling sheet from taskId query', async ({ page }) => {
  await mockTaskApi(page)

  await page.goto('/tasks/processing?taskId=task_failed_contract', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('dialog').getByText('合同审批流程 - 合同评审').first()).toBeVisible()
})
