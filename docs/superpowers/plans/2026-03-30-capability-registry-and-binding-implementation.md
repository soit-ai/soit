# Capability Registry And Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge Agent runtime capability binding on a source-agnostic registry model where runtime capabilities are `model`, `knowledge`, `workflow`, `skill`, and `tool`, and MCP-originated tools resolve through `tool_refs` instead of MCP-specific Agent binding fields.

**Architecture:** Reuse the existing in-process kernel registry as the runtime view, add a capability registry application layer to project governance objects into runtime capability entries, collapse Agent/MCP integration onto `tool_refs`, and expose one frontend capability catalog for Agent assembly and governance pages.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, existing kernel registry, React services, pytest

---

### Task 1: Add a Runtime Capability Registry Projection Layer

**Files:**
- Create: `server/app/modules/capability_registry/application/schemas.py`
- Create: `server/app/modules/capability_registry/application/service.py`
- Create: `server/app/api/v1/capabilities/router.py`
- Create: `server/app/api/v1/capabilities/handlers.py`
- Modify: `server/app/main.py`
- Test: `server/tests/entrypoints/test_capability_registry_api.py`

- [ ] **Step 1: Write the failing registry API test**

```python
def test_capability_registry_lists_runtime_capabilities(client):
    resp = client.get("/api/v1/capabilities")
    assert resp.status_code == 200
    item = resp.json()["data"]["items"][0]
    assert item["kind"] in {"model", "knowledge", "workflow", "skill", "tool"}
    assert item["source_kind"] in {"builtin", "native", "plugin", "mcp"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest server/tests/entrypoints/test_capability_registry_api.py::test_capability_registry_lists_runtime_capabilities -v`
Expected: FAIL because `/api/v1/capabilities` does not exist.

- [ ] **Step 3: Create the projection service**

```python
# server/app/modules/capability_registry/application/schemas.py
class CapabilityEntryResponse(BaseModel):
    ref: str
    kind: str
    name: str
    source_kind: str
    source_id: str | None = None
    source_version: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
```

```python
# server/app/modules/capability_registry/application/service.py
class CapabilityRegistryService:
    async def list_entries(self) -> list[CapabilityEntryResponse]:
        entries = []
        for item in get_registry().list():
            if item.kind not in {"model", "knowledge", "workflow", "skill", "tool"}:
                continue
            entries.append(...)
        return entries
```

- [ ] **Step 4: Run verification**

Run: `uv run pytest server/tests/entrypoints/test_capability_registry_api.py -v`
Expected: PASS

- [ ] **Step 5: Stage the registry API files**

Run:

```bash
git add server/app/modules/capability_registry/application/schemas.py server/app/modules/capability_registry/application/service.py server/app/api/v1/capabilities/router.py server/app/api/v1/capabilities/handlers.py server/app/main.py server/tests/entrypoints/test_capability_registry_api.py
```

Expected: files staged, no commit created.

### Task 2: Collapse MCP Agent Binding onto `tool_refs`

**Files:**
- Modify: `server/app/modules/integrations/mcp/application/service.py`
- Modify: `server/app/modules/agent/application/application_service.py`
- Modify: `server/app/modules/agent/application/schemas.py`
- Modify: `server/tests/unit/test_agent_service.py`
- Modify: `server/tests/unit/test_status_convergence.py`
- Test: `server/tests/unit/test_mcp_tool_binding_resolution.py`

- [ ] **Step 1: Write the failing MCP-to-tool binding test**

```python
def test_agent_version_accepts_mcp_tool_refs_via_tool_refs(service):
    payload = AgentVersionCreate(
        model_ref="model:openai:gpt-5.1",
        tool_refs=["mcp_tool:filesystem:read_file"],
    )
    spec = service._build_spec(payload, service._resolve_version_bindings(payload))
    assert spec["bindings"]["tool_refs"] == ["mcp_tool:filesystem:read_file"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest server/tests/unit/test_mcp_tool_binding_resolution.py::test_agent_version_accepts_mcp_tool_refs_via_tool_refs -v`
Expected: FAIL if MCP resolution still depends on source-specific binding APIs.

- [ ] **Step 3: Remove MCP-specific Agent binding vocabulary**

```python
# server/app/modules/integrations/mcp/application/service.py
@workspace_guard("read")
async def resolve_tool_refs(self, *, tool_refs: list[str] | None = None) -> dict[str, dict]:
    servers = self.repo.list(limit=500, offset=0, enabled_only=True)
    index = self._binding_target_index(servers)
    resolved = {}
    for ref in tool_refs or []:
        target = index.get(ref)
        if target and target["binding_type"] == "mcp_tool":
            resolved[ref] = dict(target)
    return resolved
```

```python
# server/app/modules/agent/application/schemas.py
class AgentCapabilityBindings(BaseModel):
    model_ref: Optional[str] = None
    knowledge_refs: Optional[List[str]] = None
    workflow_refs: Optional[List[str]] = None
    skill_refs: Optional[List[str]] = None
    plugin_refs: Optional[List[str]] = None
    tool_refs: Optional[List[str]] = None
```

- [ ] **Step 4: Run verification**

Run: `uv run pytest server/tests/unit/test_mcp_tool_binding_resolution.py server/tests/unit/test_agent_service.py -v`
Expected: PASS

- [ ] **Step 5: Stage the Agent/MCP binding convergence**

Run:

```bash
git add server/app/modules/integrations/mcp/application/service.py server/app/modules/agent/application/application_service.py server/app/modules/agent/application/schemas.py server/tests/unit/test_mcp_tool_binding_resolution.py server/tests/unit/test_agent_service.py server/tests/unit/test_status_convergence.py
```

Expected: files staged, no commit created.

### Task 3: Expose the Capability Catalog to the Web App

**Files:**
- Create: `web/app/services/capability-service.ts`
- Modify: `web/app/routes/agents/detail.tsx`
- Modify: `web/app/routes/skill/index.tsx`
- Modify: `web/app/routes/mcp/index.tsx`
- Test: `web/e2e/capability-registry.spec.ts`

- [ ] **Step 1: Write the failing capability catalog e2e**

```ts
test('capability governance pages surface runtime capability source metadata', async ({ page }) => {
  await page.goto('/mcp', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText(/source_kind/i)).toBeVisible()
  await expect(page.getByText(/tool/i)).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep "source metadata"`
Expected: FAIL because the web app does not yet consume `/api/v1/capabilities`.

- [ ] **Step 3: Add the frontend capability service**

```ts
// web/app/services/capability-service.ts
export interface CapabilityEntry {
  ref: string
  kind: 'model' | 'knowledge' | 'workflow' | 'skill' | 'tool'
  name: string
  source_kind: 'builtin' | 'native' | 'plugin' | 'mcp'
  source_id?: string | null
  source_version?: string | null
  metadata_json: Record<string, unknown>
}

export const listCapabilities = () =>
  get<PaginatedResponse<CapabilityEntry>>('/capabilities').then((response) => response.data)
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep "source metadata"`
Expected: PASS

- [ ] **Step 5: Stage the capability catalog UI wiring**

Run:

```bash
git add web/app/services/capability-service.ts web/app/routes/agents/detail.tsx web/app/routes/skill/index.tsx web/app/routes/mcp/index.tsx web/e2e/capability-registry.spec.ts
```

Expected: files staged, no commit created.

### Task 4: Surface "Bound By" and "Recent Usage" on Governance Pages

**Files:**
- Modify: `web/app/routes/knowledge/detail.tsx`
- Modify: `web/app/routes/plugin/index.tsx`
- Modify: `web/app/routes/skill/index.tsx`
- Modify: `web/app/routes/mcp/index.tsx`
- Modify: `web/app/services/capability-service.ts`
- Test: `web/e2e/capability-governance.spec.ts`

- [ ] **Step 1: Write the failing governance-usage test**

```ts
import { expect, test } from '@playwright/test'

test('governance pages show bound agents and recent runtime usage', async ({ page }) => {
  await page.goto('/plugins', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Bound By Agents')).toBeVisible()
  await expect(page.getByText('Recent Runtime Usage')).toBeVisible()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep "recent runtime usage"`
Expected: FAIL because governance pages still act as CRUD surfaces only.

- [ ] **Step 3: Add capability usage cards to governance views**

```tsx
// shared pattern for knowledge/plugin/skill/mcp pages
<Card>
  <CardHeader>
    <CardTitle>Bound By Agents</CardTitle>
  </CardHeader>
  <CardContent>{bindings.map((item) => <Badge key={item.agent_id}>{item.agent_name}</Badge>)}</CardContent>
</Card>

<Card>
  <CardHeader>
    <CardTitle>Recent Runtime Usage</CardTitle>
  </CardHeader>
  <CardContent>{recentRuns.map((run) => <div key={run.id}>{run.id}</div>)}</CardContent>
</Card>
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep "recent runtime usage"`
Expected: PASS

- [ ] **Step 5: Stage the governance usage surfaces**

Run:

```bash
git add web/app/routes/knowledge/detail.tsx web/app/routes/plugin/index.tsx web/app/routes/skill/index.tsx web/app/routes/mcp/index.tsx web/app/services/capability-service.ts web/e2e/capability-governance.spec.ts
```

Expected: files staged, no commit created.
