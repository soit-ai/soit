# Observability Workspace Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the run-list-first observability landing page with a workspace console that highlights workspace health, Agent summaries, workflow bottlenecks, model cost, knowledge retrieval quality, and tool reliability.

**Architecture:** Keep the existing run ledger as the source of truth, add workspace-level dashboard queries on top of `Run`, `RunStep`, `RunArtifact`, `RunCostEntry`, approvals, and feedback, then rebuild the `/observability` page around those summaries while keeping the run explorer as a drill-down child view.

**Tech Stack:** FastAPI, SQLAlchemy, existing run service, React Router, TanStack Query, Playwright, pytest

---

### Task 1: Add Workspace Console Summary Endpoints

**Files:**
- Create: `server/app/modules/observability/application/dashboard_schemas.py`
- Create: `server/app/modules/observability/application/dashboard_service.py`
- Modify: `server/app/api/v1/observability/router.py`
- Modify: `server/app/api/v1/observability/handlers.py`
- Test: `server/tests/entrypoints/test_observability_dashboard_api.py`

- [ ] **Step 1: Write the failing dashboard API test**

```python
def test_observability_dashboard_returns_workspace_summary(client):
    resp = client.get("/api/v1/observability/dashboard")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "workspace_summary" in data
    assert "agent_summaries" in data
    assert "tool_health" in data
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest server/tests/entrypoints/test_observability_dashboard_api.py::test_observability_dashboard_returns_workspace_summary -v`
Expected: FAIL because the dashboard endpoint does not exist.

- [ ] **Step 3: Add the dashboard query layer**

```python
# server/app/modules/observability/application/dashboard_schemas.py
class WorkspaceObservabilityDashboard(BaseModel):
    workspace_summary: dict[str, Any]
    agent_summaries: list[dict[str, Any]]
    model_costs: list[dict[str, Any]]
    workflow_bottlenecks: list[dict[str, Any]]
    tool_health: list[dict[str, Any]]
    approvals_summary: dict[str, Any]
```

```python
# server/app/api/v1/observability/router.py
@router.get("/dashboard", response_model=WorkspaceObservabilityDashboard)
async def get_dashboard(...):
    return await ObservabilityHandlers(service).get_dashboard(ctx)
```

- [ ] **Step 4: Run backend verification**

Run: `uv run pytest server/tests/entrypoints/test_observability_dashboard_api.py -v`
Expected: PASS

- [ ] **Step 5: Stage the dashboard endpoint files**

Run:

```bash
git add server/app/modules/observability/application/dashboard_schemas.py server/app/modules/observability/application/dashboard_service.py server/app/api/v1/observability/router.py server/app/api/v1/observability/handlers.py server/tests/entrypoints/test_observability_dashboard_api.py
```

Expected: files staged, no commit created.

### Task 2: Rebuild `/observability` Around Workspace Console Cards and Drill-Downs

**Files:**
- Modify: `web/app/routes/observability/index.tsx`
- Create: `web/app/services/observability-service.ts`
- Create: `web/app/routes/observability/ui/workspace-summary.tsx`
- Create: `web/app/routes/observability/ui/agent-health-table.tsx`
- Create: `web/app/routes/observability/ui/tool-health-table.tsx`
- Test: `web/e2e/observability.spec.ts`

- [ ] **Step 1: Write the failing observability UI test**

```ts
import { expect, test } from '@playwright/test'

test('observability home renders workspace console cards', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('workspace_id', 'workspace-1')
  })
  await page.goto('/observability', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Workspace Summary')).toBeVisible()
  await expect(page.getByText('Agent Health')).toBeVisible()
  await expect(page.getByText('Tool Reliability')).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep "workspace console cards"`
Expected: FAIL because `/observability` still renders recent runs plus cost summary only.

- [ ] **Step 3: Add a dashboard service and split the page into focused components**

```ts
// web/app/services/observability-service.ts
export const getObservabilityDashboard = () =>
  get<WorkspaceObservabilityDashboard>('/observability/dashboard').then((response) => response.data)
```

```tsx
// web/app/routes/observability/index.tsx
const { data: dashboard } = useQuery({
  queryKey: ['observability', 'dashboard'],
  queryFn: () => getObservabilityDashboard(),
})

return (
  <>
    <WorkspaceSummary summary={dashboard?.workspace_summary} />
    <AgentHealthTable agents={dashboard?.agent_summaries || []} />
    <ToolHealthTable tools={dashboard?.tool_health || []} />
  </>
)
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep "workspace console cards"`
Expected: PASS

- [ ] **Step 5: Stage the workspace console UI**

Run:

```bash
git add web/app/routes/observability/index.tsx web/app/services/observability-service.ts web/app/routes/observability/ui/workspace-summary.tsx web/app/routes/observability/ui/agent-health-table.tsx web/app/routes/observability/ui/tool-health-table.tsx web/e2e/observability.spec.ts
```

Expected: files staged, no commit created.

### Task 3: Add Tool, Workflow, and Retrieval Drill-Down Coverage

**Files:**
- Modify: `server/app/modules/observability/application/dashboard_service.py`
- Modify: `web/app/routes/observability/index.tsx`
- Modify: `server/tests/entrypoints/test_observability_dashboard_api.py`
- Modify: `web/e2e/observability.spec.ts`
- Test: `server/tests/entrypoints/test_observability_dashboard_api.py`

- [ ] **Step 1: Write the failing drill-down test**

```python
def test_observability_dashboard_includes_workflow_and_tool_breakdowns(client):
    resp = client.get("/api/v1/observability/dashboard")
    data = resp.json()["data"]
    assert "workflow_bottlenecks" in data
    assert "tool_health" in data
    assert "knowledge_quality" in data
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest server/tests/entrypoints/test_observability_dashboard_api.py::test_observability_dashboard_includes_workflow_and_tool_breakdowns -v`
Expected: FAIL until the dashboard schema and queries are expanded.

- [ ] **Step 3: Expand the dashboard payload and UI tabs**

```python
# server/app/modules/observability/application/dashboard_service.py
return WorkspaceObservabilityDashboard(
    workspace_summary=workspace_summary,
    agent_summaries=agent_summaries,
    model_costs=model_costs,
    workflow_bottlenecks=workflow_bottlenecks,
    tool_health=tool_health,
    knowledge_quality=knowledge_quality,
    approvals_summary=approvals_summary,
)
```

```tsx
// web/app/routes/observability/index.tsx
<Tabs defaultValue="agents">
  <TabsTrigger value="agents">Agent Health</TabsTrigger>
  <TabsTrigger value="workflows">Workflow Bottlenecks</TabsTrigger>
  <TabsTrigger value="tools">Tool Reliability</TabsTrigger>
  <TabsTrigger value="knowledge">Knowledge Quality</TabsTrigger>
</Tabs>
```

- [ ] **Step 4: Run verification**

Run: `uv run pytest server/tests/entrypoints/test_observability_dashboard_api.py -v`
Expected: PASS

Run: `npm run test:e2e -- --grep observability`
Expected: PASS

- [ ] **Step 5: Stage the drill-down expansion**

Run:

```bash
git add server/app/modules/observability/application/dashboard_service.py server/tests/entrypoints/test_observability_dashboard_api.py web/app/routes/observability/index.tsx web/e2e/observability.spec.ts
```

Expected: files staged, no commit created.
