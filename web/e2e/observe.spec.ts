import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const pageReadyTimeout = 45_000

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const tabs = [
  { id: 'agent_health', label: 'Agent 健康', rowId: 'agent:support' },
  { id: 'workflow_bottlenecks', label: '工作流瓶颈', rowId: 'tool-call' },
  { id: 'tool_reliability', label: '工具可靠性', rowId: 'search_tool' },
  { id: 'knowledge_quality', label: '知识质量', rowId: 'knowledge:kb_support' },
]

function baseDashboard(tab: string, q = '') {
  const rowsByTab: Record<string, Array<Record<string, unknown> & { id: string }>> = {
    agent_health: [
      { id: 'agent:support', name: 'agent:support', status: 'warning', run_count: 3, failed_run_count: 1, success_rate: 0.667, avg_latency_ms: 186, last_error: 'timeout', owner: 'Jude', last_run_at: '2026-06-01T20:45:00Z', latest_run_id: 'run-dashboard-latest', latest_run_status: 'failed', latest_run_cost_usd: 1.25, latest_failure_reason: 'timeout', detail_url: '/observe/runs/run-dashboard-latest' },
    ],
    workflow_bottlenecks: [
      { id: 'tool-call', name: 'tool-call', stage: '工具调用', current_queue: 76, avg_wait_ms: 1400, failure_rate: 0.012, affected_agents: ['agent:support'], owner: 'Jude', latest_run_id: 'run-dashboard-workflow', latest_run_status: 'failed', latest_run_cost_usd: 0.8, latest_failure_reason: 'queue timeout', detail_url: '/observe/runs/run-dashboard-workflow' },
    ],
    tool_reliability: [
      { id: 'search_tool', name: 'search_tool', type: '查询工具', call_count: 12, success_rate: 0.978, avg_latency_ms: 312, failure_reason: { timeout: 1 }, related_agents: ['agent:support'], owner: 'Alice', status: 'warning', latest_run_id: 'run-dashboard-tool', latest_run_status: 'failed', latest_run_cost_usd: 0.5, latest_failure_reason: 'tool timeout', detail_url: '/observe/runs/run-dashboard-tool' },
    ],
    knowledge_quality: [
      { id: 'knowledge:kb_support', name: 'knowledge:kb_support', related_agents: ['agent:support'], hit_rate: 0.962, missing_answer_rate: 0.038, expired_chunks: 8, last_updated: '2026-06-01 18:20', status: 'healthy', owner: 'Jude', latest_run_id: 'run-dashboard-knowledge', latest_run_status: 'succeeded', latest_run_cost_usd: 0.3, latest_failure_reason: null, detail_url: '/observe/runs/run-dashboard-knowledge' },
    ],
  }
  const rows = rowsByTab[tab].filter((row) => !q || row.id.includes(q) || String(row.name).includes(q))
  return {
    overview: {
      workspace_health_score: 98.6,
      workspace_health_status: 'healthy',
      active_alert_count: 3,
      sampling_rate: 1,
      sampling_status: 'full',
      refreshed_at: '2026-06-01T20:45:00Z',
    },
    metric_cards: [
      { id: 'run_count', label: '运行次数', value: '234', delta: '+12.4%', trend: [1, 3, 2, 5], tone: 'blue', run_id: 'run-dashboard-latest', detail_url: '/observe/runs/run-dashboard-latest', status: 'failed', cost_usd: 1.25, failure_reason: 'timeout' },
      { id: 'failed_run_count', label: '失败运行', value: '45', delta: '+28.6%', trend: [1, 2, 1, 3], tone: 'red', run_id: 'run-dashboard-latest', detail_url: '/observe/runs/run-dashboard-latest', status: 'failed', cost_usd: 1.25, failure_reason: 'timeout' },
      { id: 'active_run_count', label: '活跃运行', value: '18', delta: '-10.0%', trend: [2, 4, 3], tone: 'cyan' },
      { id: 'pending_approvals', label: '待审批', value: '0', delta: '0', trend: [0], tone: 'amber' },
      { id: 'total_cost_usd', label: '成本 (USD)', value: '0.00', delta: '0', trend: [0], tone: 'green' },
    ],
    priority_alert: {
      priority: 'P1',
      title: 'Workflow 队列延迟上升',
      started_at: '2026-06-01T20:35:00Z',
      scope: '3 个工作区',
      affected_agents: 12,
      duration_label: '18 分钟',
      detail_url: '/observe/runs',
    },
    recent_runs: [
      {
        run_id: 'run-dashboard-latest',
        mode: 'agent',
        kind: 'agent',
        subject_kind: 'agent',
        subject_id: 'agent:support',
        status: 'failed',
        cost_usd: 1.25,
        failure_reason: 'timeout',
        started_at: '2026-06-01T20:45:00Z',
        duration_ms: 1240,
        observe_summary: {
          step_count: 6,
          tool_call_count: 1,
          child_run_count: 1,
          response_event_count: 4,
          citation_count: 2,
          audit_count: 1,
          cost_entry_count: 3,
        },
        detail_url: '/observe/runs/run-dashboard-latest',
      },
    ],
    tabs: tabs.map((item) => ({ id: item.id, label: item.label, count: 1 })),
    section: {
      id: tab,
      summary_cards: [
        { id: `${tab}_summary`, label: '摘要', value: '1', delta: null, trend: [1], tone: 'green' },
      ],
      charts: {
        trend: [
          { bucket: '2026-06-01T20:30:00Z', run_count: 3, failed_run_count: 1, tool_count: 2, tool_failed_count: 1, retrieval_count: 2, retrieval_failed_count: 0, success_rate: 0.667 },
        ],
        health_distribution: [{ status: 'healthy', count: 1 }],
        alert_compression: { raw_alerts: 2, compressed_alerts: 1 },
        queue_distribution: rows,
        error_distribution: [{ type: 'timeout', count: 1 }],
        quality_score: 92.4,
        low_quality_sources: rows,
      },
      rows,
      page: { page_size: rows.length, next_page_token: null, total_count: rows.length },
      empty_state: { title: '暂无数据', description: '当前时间范围内没有可展示的观测数据。' },
    },
    workspace_summary: { run_count: 4, failed_run_count: 1, active_run_count: 1, pending_approvals: 2, feedback_count: 3, total_cost_usd: 1.25 },
    agent_summaries: [],
    model_costs: [],
    workflow_bottlenecks: [],
    tool_health: [],
    knowledge_quality: [],
    approvals_summary: { pending: 2, approved: 4, rejected: 1 },
  }
}

async function mockObserveApi(page: Page) {
  await page.route('**/api/v1/observe/dashboard**', async (route) => {
    const url = new URL(route.request().url())
    const tab = url.searchParams.get('tab') || 'agent_health'
    const q = url.searchParams.get('q') || ''
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: baseDashboard(tab, q) }),
    })
  })
}

async function mockRunExplorerApi(page: Page) {
  const run = {
    id: 'run-dashboard-latest',
    trace_id: 'trace-dashboard',
    user_id: 'user-1',
    mode: 'agent',
    kind: 'agent',
    subject_kind: 'agent',
    subject_id: 'agent:support',
    subject_version_id: 'enterprise-mvp-agent',
    status: 'succeeded',
    input_summary: 'refund escalation',
    output_summary: 'review ticket created',
    started_at: '2026-06-01T20:45:00Z',
    ended_at: '2026-06-01T20:45:01Z',
    duration_ms: 1240,
    created_at: '2026-06-01T20:45:00Z',
    updated_at: '2026-06-01T20:45:01Z',
    observe_summary: {
      step_count: 6,
      tool_call_count: 1,
      child_run_count: 1,
      response_event_count: 4,
      citation_count: 2,
      audit_count: 1,
      cost_entry_count: 3,
    },
  }
  const costSummary = {
    tokens_prompt: 12,
    tokens_completion: 18,
    embedding_count: 1,
    rerank_count: 0,
    ms_total: 1240,
    storage_bytes: 0,
  }

  await page.route('**/api/v1/runs/costs/summary**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: costSummary }) })
  })
  await page.route('**/api/v1/runs/costs/by-day**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [{ date: '2026-06-01', tokens_prompt: 12, tokens_completion: 18, embedding_count: 1, rerank_count: 0, ms_total: 1240, storage_bytes: 0 }] }) })
  })
  await page.route('**/api/v1/runs/costs/by-provider**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [{ provider: 'test', ...costSummary }] }) })
  })
  await page.route('**/api/v1/runs/costs/by-model**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [{ model_ref: 'model:test:support-ticket', ...costSummary }] }) })
  })
  await page.route('**/api/v1/runs/*', async (route) => {
    const runId = new URL(route.request().url()).pathname.split('/').pop() || run.id
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          run: { ...run, id: runId },
          steps: [],
          artifacts: [],
          cost_summary: costSummary,
          costs: [],
          response_events: [],
          tool_calls: [],
          citations: [],
          audits: [],
          child_runs: [],
        },
      }),
    })
  })
  await page.route('**/api/v1/runs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [run],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })
}

async function mockLegacyObserveApi(page: Page) {
  await page.unroute('**/api/v1/observe/dashboard**')
  await page.route('**/api/v1/observe/dashboard**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          workspace_summary: {
            run_count: 10,
            failed_run_count: 2,
            active_run_count: 1,
            pending_approvals: 3,
            feedback_count: 0,
            total_cost_usd: 4.5,
          },
          agent_summaries: [
            {
              agent_id: 'legacy-agent',
              run_count: 10,
              failed_run_count: 2,
              last_run_at: '2026-06-01T20:45:00Z',
            },
          ],
          model_costs: [],
          workflow_bottlenecks: [],
          tool_health: [],
          knowledge_quality: [],
          approvals_summary: { pending: 3, approved: 0, rejected: 0 },
        },
      }),
    })
  })
}

async function mockEmptyObserveApi(page: Page) {
  await page.unroute('**/api/v1/observe/dashboard**')
  await page.route('**/api/v1/observe/dashboard**', async (route) => {
    const url = new URL(route.request().url())
    const tab = url.searchParams.get('tab') || 'agent_health'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          ...baseDashboard(tab),
          recent_runs: [],
          tabs: tabs.map((item) => ({ id: item.id, label: item.label, count: 0 })),
          section: {
            id: tab,
            summary_cards: [],
            charts: { trend: [], health_distribution: [], queue_distribution: [], error_distribution: [], low_quality_sources: [] },
            rows: [],
            page: { page_size: 0, next_page_token: null, total_count: 0 },
            empty_state: {
              title: `暂无${tabs.find((item) => item.id === tab)?.label || '观测'}数据`,
              description: '当前时间范围内没有对应应用观测数据。',
            },
          },
          workspace_summary: { run_count: 0, failed_run_count: 0, active_run_count: 0, pending_approvals: 0, feedback_count: 0, total_cost_usd: 0 },
          agent_summaries: [],
          workflow_bottlenecks: [],
          tool_health: [],
          knowledge_quality: [],
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockObserveApi(page)
  await mockRunExplorerApi(page)
})

test('observe dashboard keeps tab state in the URL', async ({ page }) => {
  await page.goto('/observe?tab=tool_reliability&range=1h&bucket=10m', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: '观测工作台' })).toBeVisible({ timeout: pageReadyTimeout })
  await expect(page.getByRole('tab', { name: '工具可靠性' })).toHaveAttribute('data-state', 'active')
  await expect(page.getByRole('row').filter({ hasText: 'search_tool' })).toBeVisible()

  await page.getByRole('tab', { name: '知识质量' }).click()
  await expect(page).toHaveURL(/tab=knowledge_quality/)
  await expect(page.getByRole('row').filter({ hasText: 'knowledge:kb_support' })).toBeVisible()
})

test('observe dashboard defaults to 24h but preserves explicit range', async ({ page }) => {
  await page.goto('/observe', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: '观测工作台' })).toBeVisible({ timeout: pageReadyTimeout })
  await expect(page.getByLabel('时间范围')).toHaveValue('24h')
  await page.getByLabel('时间范围').selectOption('1h')
  await expect(page).toHaveURL(/range=1h/)
  await expect(page.getByLabel('时间范围')).toHaveValue('1h')
})

test('observe search updates the current tab query', async ({ page }) => {
  await page.goto('/observe?tab=tool_reliability', { waitUntil: 'domcontentloaded' })

  await page.getByPlaceholder('搜索名称').fill('missing')

  await expect(page).toHaveURL(/q=missing/)
  await expect(page.getByText('暂无数据')).toBeVisible()
})

test('observe run explorer action is available', async ({ page }) => {
  await page.goto('/observe?tab=agent_health', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: '观测工作台' })).toBeVisible({ timeout: pageReadyTimeout })

  await page.getByRole('link', { name: '打开 Run Explorer' }).first().click()

  await expect(page).toHaveURL(/\/observe\/runs/)
  await expect(page).toHaveURL(/include_observe_summary=true/)
})

test('observe dashboard cards and rows link to run detail', async ({ page }) => {
  await page.goto('/observe?tab=tool_reliability', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: '观测工作台' })).toBeVisible({ timeout: pageReadyTimeout })

  await page.getByRole('button', { name: '打开运行详情：运行次数' }).click()
  await expect(page).toHaveURL(/\/observe\/runs\/run-dashboard-latest/)

  await page.goBack({ waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: '观测工作台' })).toBeVisible({ timeout: pageReadyTimeout })
  await page.getByRole('row').filter({ hasText: 'search_tool' }).getByRole('button', { name: '查看运行' }).click()
  await expect(page).toHaveURL(/\/observe\/runs\/run-dashboard-tool/)
})

test('observe dashboard surfaces recent run observability summary', async ({ page }) => {
  await page.goto('/observe', { waitUntil: 'domcontentloaded' })

  const recentRun = page.getByRole('button', { name: /打开运行详情：run-dashboard-latest/ })
  await expect(recentRun).toBeVisible({ timeout: pageReadyTimeout })
  await expect(recentRun).toContainText('agent · agent:support')
  await expect(recentRun).toContainText('1.24s')
  await expect(recentRun).toContainText('步骤 6')
  await expect(recentRun).toContainText('工具 1')
  await expect(recentRun).toContainText('引用 2')
  await expect(recentRun).toContainText('审计 1')

  await recentRun.click()
  await expect(page).toHaveURL(/\/observe\/runs\/run-dashboard-latest/)
})

test('observe dashboard renders legacy payloads without the new section fields', async ({ page }) => {
  await mockLegacyObserveApi(page)

  await page.goto('/observe?tab=agent_health', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: '观测工作台' })).toBeVisible({ timeout: pageReadyTimeout })
  await expect(page.getByText('80%').first()).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: 'legacy-agent' })).toBeVisible()
})

test('observe tabs show diagnostic empty state with run explorer entry', async ({ page }) => {
  await mockEmptyObserveApi(page)

  await page.goto('/observe?tab=tool_reliability', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('当前时间范围内没有对应应用观测数据。')).toBeVisible({ timeout: pageReadyTimeout })
  await page.getByRole('link', { name: '打开 Run Explorer' }).first().click()
  await expect(page).toHaveURL(/\/observe\/runs/)
})
