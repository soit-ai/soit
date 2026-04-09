# P0 Semantic Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove runtime-facing `App/Application/Dataset` semantics from SOIT's frontend copy, route vocabulary, and backend compatibility surface without breaking the Agent-centered API.

**Architecture:** Frontend text and route vocabulary converges first, then backend compatibility aliases are removed or narrowed, then anti-regression checks are added so old terms do not leak back into product pages or response schemas. Keep legacy-offline tests, but stop serving compatibility fields and names from active runtime APIs.

**Tech Stack:** React Router 7, i18next, Playwright, FastAPI, Pydantic, pytest, ripgrep

---

### Task 1: Rename Frontend Lexicon and Locale Loading

**Files:**
- Create: `web/app/i18n/en-US/agent.ts`
- Create: `web/app/i18n/zh-CN/agent.ts`
- Modify: `web/app/i18n/i18next-config.ts`
- Modify: `web/app/components/nav/root-sidebar.tsx`
- Modify: `web/app/routes/agents/index.tsx`
- Modify: `web/app/routes/index/index.tsx`
- Test: `web/e2e/terminology.spec.ts`

- [ ] **Step 1: Write the failing terminology smoke test**

```ts
import { expect, test } from '@playwright/test'

test('workspace surfaces do not expose legacy app terminology', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('workspace_id', 'workspace-1')
  })

  await page.goto('/agents', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText(/Create App|New App|应用类型|应用设置/)).toHaveCount(0)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:e2e -- --grep terminology`
Expected: FAIL because current locale bundles and hero copy still expose `App` strings.

- [ ] **Step 3: Replace locale namespace loading and visible labels**

```ts
// web/app/i18n/i18next-config.ts
const resources = {
  translation: {
    agent: (await import(`./${lang}/agent.ts`)).default,
    chat: (await import(`./${lang}/chat.ts`)).default,
    common: (await import(`./${lang}/common.ts`)).default,
    // remove app.ts from active loading once consumers are migrated
  },
}
```

```tsx
// web/app/components/nav/root-sidebar.tsx
const data = {
  navApp: [
    { title: 'Agents', url: '/agents', type: 'agents', icon: Bot, isNav: true },
    { title: 'Chat', url: '/chat', type: 'chat', icon: MessageCircleMore, isNav: true },
    { title: 'Workflow', url: '/workflow', type: 'workflow', icon: Workflow, isNav: true },
    { title: 'Knowledge', url: '/knowledge', type: 'knowledge', icon: ScrollText, isNav: true },
    { title: 'Tasks', url: '/tasks', type: 'tasks', icon: Command, isNav: true },
    { title: 'Observability', url: '/observability', type: 'observability', icon: Activity, isNav: true },
  ],
}
```

- [ ] **Step 4: Run verification**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:e2e -- --grep terminology`
Expected: PASS

- [ ] **Step 5: Stage the frontend lexicon changes**

Run:

```bash
git add web/app/i18n/i18next-config.ts web/app/i18n/en-US/agent.ts web/app/i18n/zh-CN/agent.ts web/app/components/nav/root-sidebar.tsx web/app/routes/agents/index.tsx web/app/routes/index/index.tsx web/e2e/terminology.spec.ts
```

Expected: files staged, no commit created.

### Task 2: Remove Knowledge Compatibility Fields and Legacy Route Language

**Files:**
- Modify: `server/app/modules/knowledge/application/schemas.py`
- Modify: `server/tests/entrypoints/test_knowledge_api.py`
- Modify: `server/tests/entrypoints/test_thread_api.py`
- Test: `server/tests/entrypoints/test_knowledge_api.py`

- [ ] **Step 1: Write the failing backend response test**

```python
def test_knowledge_response_does_not_expose_legacy_source_type(client):
    resp = client.get("/api/v1/knowledge", headers=_headers())
    assert resp.status_code == 200
    item = resp.json()["data"]["items"][0]
    assert "source_type" not in item
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest server/tests/entrypoints/test_knowledge_api.py::test_knowledge_response_does_not_expose_legacy_source_type -v`
Expected: FAIL because `KnowledgeResponse` still includes `source_type`.

- [ ] **Step 3: Remove the compatibility alias and tighten legacy-offline coverage**

```python
# server/app/modules/knowledge/application/schemas.py
class KnowledgeResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    status: str
    visibility: str
    knowledge_type: str
    settings_json: dict[str, Any]
    chunking_json: dict[str, Any]
    retrieval_json: dict[str, Any]
    # remove source_type compatibility alias
```

```python
# server/tests/entrypoints/test_thread_api.py
def test_legacy_chat_endpoints_are_offline(client):
    ...
    assert completions_response.status_code == status.HTTP_404_NOT_FOUND
    assert stream_response.status_code == status.HTTP_404_NOT_FOUND
```

- [ ] **Step 4: Run backend verification**

Run: `uv run pytest server/tests/entrypoints/test_knowledge_api.py server/tests/entrypoints/test_thread_api.py -v`
Expected: PASS

- [ ] **Step 5: Stage the backend compatibility cleanup**

Run:

```bash
git add server/app/modules/knowledge/application/schemas.py server/tests/entrypoints/test_knowledge_api.py server/tests/entrypoints/test_thread_api.py
```

Expected: files staged, no commit created.

### Task 3: Add Anti-Regression Guards for Forbidden Runtime Vocabulary

**Files:**
- Modify: `server/scripts/refactor_guardrails.py`
- Create: `web/e2e/legacy-vocabulary.spec.ts`
- Test: `server/scripts/refactor_guardrails.py`

- [ ] **Step 1: Write the failing vocabulary guard test**

```ts
import { expect, test } from '@playwright/test'

test('agent workspace routes do not show app vocabulary', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('workspace_id', 'workspace-1')
  })
  await page.goto('/chat', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText(/\bApp\b|应用设置|应用参数/)).toHaveCount(0)
})
```

- [ ] **Step 2: Run the guard test to verify it fails or is missing**

Run: `npm run test:e2e -- --grep "app vocabulary"`
Expected: FAIL because the spec file does not exist yet or current copy still matches forbidden terms.

- [ ] **Step 3: Expand the repo guardrail patterns**

```python
# server/scripts/refactor_guardrails.py
FORBIDDEN_RUNTIME_TERMS = [
    r"\bApp\b",
    r"\bApplication\b",
    r"\bDataset\b",
    r"legacy_app_ref",
    r"dataset_id",
]
```

- [ ] **Step 4: Run verification**

Run: `uv run python server/scripts/refactor_guardrails.py`
Expected: PASS for allowed files, non-zero only if new forbidden runtime terms remain in active code paths.

Run: `npm run test:e2e -- --grep "app vocabulary"`
Expected: PASS

- [ ] **Step 5: Stage the guardrails**

Run:

```bash
git add server/scripts/refactor_guardrails.py web/e2e/legacy-vocabulary.spec.ts
```

Expected: files staged, no commit created.
