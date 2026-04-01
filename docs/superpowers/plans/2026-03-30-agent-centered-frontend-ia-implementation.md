# Agent-Centered Frontend IA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the web app into an Agent-centered workspace where `Agents` is the assembly console, `Chat` is the Agent-focused workbench, and the root navigation reflects the `assemble -> use -> observe` model.

**Architecture:** Reorder the root sidebar, add first-level governance routes for `Skills` and `MCP`, rework `/chat` to default to the last used Agent and its last thread, and reshape `/agents` detail into an assembly-first surface using existing Agent APIs. Use Playwright for route-level smoke coverage and `npm run typecheck` for structural verification.

**Tech Stack:** React Router 7, React 19, TanStack Query, localStorage, Playwright

---

### Task 1: Reorder Root Navigation and Add First-Level Governance Routes

**Files:**
- Modify: `web/app/routes.ts`
- Modify: `web/app/components/nav/root-sidebar.tsx`
- Create: `web/app/routes/skill/index.tsx`
- Create: `web/app/routes/mcp/index.tsx`
- Modify: `web/e2e/agent.spec.ts`
- Test: `web/e2e/navigation.spec.ts`

- [ ] **Step 1: Write the failing navigation smoke test**

```ts
import { expect, test } from '@playwright/test'

test('root navigation shows agent-centered order', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('workspace_id', 'workspace-1')
  })

  await page.goto('/agents', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('link', { name: /Agents/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Chat/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Observability/i })).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep "agent-centered order"`
Expected: FAIL because `Skills` and `MCP` routes do not exist and the sidebar order still reflects the old menu.

- [ ] **Step 3: Implement the route and sidebar changes**

```ts
// web/app/routes.ts
...prefix('/skills', [
  index('./routes/skill/index.tsx'),
]),
...prefix('/mcp', [
  index('./routes/mcp/index.tsx'),
]),
```

```tsx
// web/app/components/nav/root-sidebar.tsx
const navApp = [
  { title: 'Agents', url: '/agents', type: 'agents', icon: Bot, isNav: true },
  { title: 'Chat', url: '/chat', type: 'chat', icon: MessageCircleMore, isNav: true },
  { title: 'Workflow', url: '/workflow', type: 'workflow', icon: Workflow, isNav: true },
  { title: 'Knowledge', url: '/knowledge', type: 'knowledge', icon: ScrollText, isNav: true },
  { title: 'Skills', url: '/skills', type: 'skills', icon: Sparkles, isNav: true },
  { title: 'Plugins', url: '/plugins', type: 'plugins', icon: Unplug, isNav: true },
  { title: 'MCP', url: '/mcp', type: 'mcp', icon: Cable, isNav: true },
  { title: 'Tasks', url: '/tasks', type: 'tasks', icon: Command, isNav: true },
  { title: 'Observability', url: '/observability', type: 'observability', icon: Activity, isNav: true },
]
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep "agent-centered order"`
Expected: PASS

- [ ] **Step 5: Stage the route and sidebar changes**

Run:

```bash
git add web/app/routes.ts web/app/components/nav/root-sidebar.tsx web/app/routes/skill/index.tsx web/app/routes/mcp/index.tsx web/e2e/navigation.spec.ts
```

Expected: files staged, no commit created.

### Task 2: Turn `/chat` into an Agent-Focused Workbench

**Files:**
- Modify: `web/app/routes/chat/index.tsx`
- Modify: `web/app/routes/chat/ui/box-sidebar.tsx`
- Modify: `web/app/services/thread-service.ts`
- Modify: `web/e2e/chat.spec.ts`
- Test: `web/e2e/chat.spec.ts`

- [ ] **Step 1: Write the failing workbench behavior test**

```ts
test('chat defaults to the last used agent and opens its last thread', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('chat_last_agent_id', 'agent-1')
  })

  await page.goto('/chat', { waitUntil: 'domcontentloaded' })
  await expect(page.getByDisplayValue(/Demo Agent/)).toBeVisible()
  await expect(page.getByText('Demo Thread')).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep "last used agent"`
Expected: FAIL because `/chat` still falls back to `default` and does not persist the Agent selection.

- [ ] **Step 3: Persist the selected Agent and redirect to the Agent's last thread**

```tsx
// web/app/routes/chat/index.tsx
const CHAT_LAST_AGENT_KEY = 'chat_last_agent_id'

useEffect(() => {
  if (agentId && agentId !== 'default') {
    localStorage.setItem(CHAT_LAST_AGENT_KEY, agentId)
  }
}, [agentId])

useEffect(() => {
  if (agentId === 'default') {
    const remembered = localStorage.getItem(CHAT_LAST_AGENT_KEY)
    if (remembered) {
      navigate(`/chat/${remembered}`)
    }
  }
}, [agentId, navigate])
```

```tsx
// web/app/routes/chat/ui/box-sidebar.tsx
const response = await listThreads({
  page_size: 100,
  status: statusFilter === 'all' ? undefined : statusFilter,
  agent_id: agentId,
})
const nextConversation = response.items[0]
if (!id && nextConversation) {
  navigate(`/chat/${agentId}/${nextConversation.id}`)
}
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep "last used agent"`
Expected: PASS

- [ ] **Step 5: Stage the chat workbench changes**

Run:

```bash
git add web/app/routes/chat/index.tsx web/app/routes/chat/ui/box-sidebar.tsx web/app/services/thread-service.ts web/e2e/chat.spec.ts
```

Expected: files staged, no commit created.

### Task 3: Reshape Agent Detail into an Assembly Console

**Files:**
- Modify: `web/app/routes/agents/detail.tsx`
- Modify: `web/app/services/agent-service.ts`
- Modify: `web/e2e/agent.spec.ts`
- Test: `web/e2e/agent.spec.ts`

- [ ] **Step 1: Write the failing assembly-console test**

```ts
test('agent detail exposes assembly-first actions', async ({ page }) => {
  await page.goto('/agents/agent-1', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Bindings')).toBeVisible()
  await expect(page.getByRole('button', { name: /Open Chat/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /View Runs/i })).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep "assembly-first actions"`
Expected: FAIL because the detail page still behaves like a mixed profile/runtime page.

- [ ] **Step 3: Group Agent detail sections around assembly**

```tsx
// web/app/routes/agents/detail.tsx
const bindingGroups = {
  model: bindings.filter((item) => item.binding_type === 'model'),
  knowledge: bindings.filter((item) => item.binding_type === 'knowledge'),
  workflow: bindings.filter((item) => item.binding_type === 'workflow'),
  skill: bindings.filter((item) => item.binding_type === 'skill'),
  plugin: bindings.filter((item) => item.binding_type === 'plugin'),
  tool: bindings.filter((item) => item.binding_type === 'tool'),
}
```

```tsx
<Button variant="secondary" onClick={() => navigate(`/observability?agent_id=${agentId}`)}>
  View Runs
</Button>
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep "assembly-first actions"`
Expected: PASS

- [ ] **Step 5: Stage the Agent detail changes**

Run:

```bash
git add web/app/routes/agents/detail.tsx web/app/services/agent-service.ts web/e2e/agent.spec.ts
```

Expected: files staged, no commit created.

### Task 4: Reprioritize `/tasks` as an Execution Control Surface

**Files:**
- Modify: `web/app/routes/tasks/index.tsx`
- Modify: `web/app/services/task-service.ts`
- Create: `web/e2e/tasks.spec.ts`
- Test: `web/e2e/tasks.spec.ts`

- [ ] **Step 1: Write the failing tasks control-surface test**

```ts
import { expect, test } from '@playwright/test'

test('tasks page prioritizes actionable work', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('workspace_id', 'workspace-1')
  })
  await page.goto('/tasks', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Pending Approvals')).toBeVisible()
  await expect(page.getByText('Failed Tasks')).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep "actionable work"`
Expected: FAIL because `/tasks` still behaves like a generic list instead of a control-first dashboard.

- [ ] **Step 3: Group tasks by actionability**

```tsx
// web/app/routes/tasks/index.tsx
const sections = {
  approvals: tasks.filter((task) => task.status === 'awaiting_approval'),
  blocked: tasks.filter((task) => task.status === 'blocked'),
  failed: tasks.filter((task) => task.status === 'failed'),
  retryable: tasks.filter((task) => task.status === 'retryable'),
}
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep "actionable work"`
Expected: PASS

- [ ] **Step 5: Stage the tasks page changes**

Run:

```bash
git add web/app/routes/tasks/index.tsx web/app/services/task-service.ts web/e2e/tasks.spec.ts
```

Expected: files staged, no commit created.
