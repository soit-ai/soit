# Agent Demo (P2-01)

This note provides a minimal demo flow for the Agent runtime and built-in tools.

## Demo: agent + dataset retrieval tool

Tool ref: `tool:function:dataset_query`

Example request (HTTP):

```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -H "X-Workspace-Id: <workspace_id>" \
  -d '{
    "messages": [
      { "role": "user", "content": "Find the key points about onboarding." }
    ],
    "tool_refs": ["tool:function:dataset_query"],
    "model": "model:openai:gpt-4o-mini",
    "max_iterations": 4
  }'
```

Notes:
- The agent may call `tool:function:dataset_query` when it needs retrieval context.
- The dataset tool expects `dataset_id` and `query` in tool parameters.
- All agent runs emit run/step/cost traces for observability.

Implementation:
- Entry point: `app/app/modules/dataset/application/tools.py`
- The tool resolves `tenant_id`, `workspace_id`, and `user_id` from the injected `ctx` or explicit fields.
