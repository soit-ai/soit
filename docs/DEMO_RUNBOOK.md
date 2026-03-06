# Demo Runbook (v0.9)

This runbook covers the three required demo scenarios in `docs/SOIT_DELIVERABLE_PLAN.md`.

## Prerequisites

1) Copy env file and set required values:
   - `cp .env.example .env`
   - Set `OPENAI_API_KEY` (or your provider key)
   - If using Vault for secrets: set `VAULT_URL` and `VAULT_TOKEN`

2) Start services:
   - `docker compose up -d`

3) Migrations + bootstrap + dataset worker are handled by compose jobs:
   - `migrate` will run `alembic upgrade head`
   - `bootstrap` will create the default admin user/tenant/workspace
   - `dataset-worker` will consume ingest tasks in the background
   - Save the printed `access_token`, `tenant_id`, `workspace_id` from `bootstrap` logs

4) (Optional) Manual scripts for debugging:
   - `docker compose run --rm api uv run alembic upgrade head`
   - `docker compose run --rm api uv run python scripts/bootstrap_admin.py --email admin@example.com --password changeme123`
   - `docker compose run --rm api uv run python scripts/dataset_ingest_worker.py --tenant-id <tenant_id> --workspace-id <workspace_id>`

## Common curl variables

```bash
export API_BASE="http://localhost:9200/api/v1"
export TOKEN="<access_token>"
export WORKSPACE_ID="<workspace_id>"
```

Headers used below:
- `Authorization: Bearer $TOKEN`
- `X-Workspace-Id: $WORKSPACE_ID`

## Scenario A: Chat + Dataset RAG

1) Create dataset:
```bash
curl -sS -X POST "$API_BASE/datasets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "Content-Type: application/json" \
  -d '{"name":"demo-dataset","type":"document","visibility":"workspace","description":"demo"}'
```

2) Upload a document (async ingest by default):
```bash
curl -sS -X POST "$API_BASE/datasets/<dataset_id>/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -F "doc_key=demo-doc" \
  -F "source_type=upload" \
  -F "file=@/path/to/demo.txt"
```

3) Wait for ingestion to finish (check in UI → Dataset → Documents / Tasks).

4) Query dataset to verify retrieval:
```bash
curl -sS -X POST "$API_BASE/datasets/<dataset_id>/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "Content-Type: application/json" \
  -d '{"query":"your question","top_k":3}'
```

5) Chat with RAG:
```bash
curl -sS -X POST "$API_BASE/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "Content-Type: application/json" \
  -d '{
        "messages":[{"role":"user","content":"your question"}],
        "rag":{"dataset_ids":["<dataset_id>"],"top_k":3}
      }'
```

6) Open Runs UI and verify run/steps/cost:
   - Web → Runs

## Scenario B: Workflow 编排与观测

1) Web → Workflow → 新建 workflow。
2) 使用 5 节点：LLM → If → ToolInvoke → SetVar → LLM（或 HTTP 节点）。
3) 保存并发布（Workflow → Publish）。
4) 在 Monitor 页面触发执行，观察实时 steps（SSE）。
5) 在 Log 页面查看历史 steps 与错误详情。
6) Retry 失败节点并确认 Run/Cost 差异。

## Scenario C: Secrets 注入工具调用

1) 配置 Vault 并写入 secret（示例）:
```bash
vault kv put secret/soit/tool_token value="your-token"
```

2) 设置工具调用 payload 中的 `secret_ref`（例如 headers/query/body）:
```json
{
  "headers": {
    "Authorization": {
      "secret_ref": "secret:soit/tool_token:value"
    }
  }
}
```

3) 通过 workflow 或 tool node 调用该工具。
4) 在 Runs / Audit 中确认无明文泄露，仅保留 `secret_ref`。

## Verification checklist

- Dataset ingestion 任务状态可见且可重试
- Chat RAG 回答包含 citations
- Workflow Monitor/Log 实时可见
- Runs/Cost 数据完整
- Secret 未以明文出现在日志/Trace/Artifact

## Smoke tests (optional)

From `app/`:

```bash
uv run python scripts/smoke/run_all.py
```

Use `--strict` to fail on skipped LLM-dependent steps.
