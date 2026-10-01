# Claude Code through SOIT

Claude Code talks to the Anthropic Messages API, which SOIT serves at
`/v1/messages`. Point it at SOIT and its model calls become governed gateway
runs: rate limits, quotas, budgets, content safety, cost and audit apply, and
each call is visible in Observe with `source=gateway`.

```bash
export ANTHROPIC_BASE_URL=http://localhost:9200      # no /v1
export ANTHROPIC_AUTH_TOKEN=sk_...                   # a SOIT API key, Settings > API
export ANTHROPIC_MODEL=model:anthropic:claude-sonnet-5-5
export ANTHROPIC_SMALL_FAST_MODEL=model:anthropic:claude-haiku-4-5-20251001
claude
```

Use model refs exactly as `GET /v1/models` lists them (`model:{provider}:{model}`
or a virtual model, `vmodel:{slug}`). Claude Code uses a second, smaller model
for background work; set it (`ANTHROPIC_SMALL_FAST_MODEL`, or
`ANTHROPIC_DEFAULT_HAIKU_MODEL` in newer versions) to a ref the key may call,
or those calls are refused.

CI runs the Anthropic Python SDK against `/v1/messages`, not Claude Code
itself. Claude Code is built on that SDK's wire format, but a live session
against SOIT has not been recorded; if one of its requests is refused, the
`400` names the field.

What to expect:

- The calls run on whichever provider the model ref names, so a virtual model
  can fail over between providers and a budget can stop a session that spends
  too much.
- `thinking`, prompt-caching hints (`cache_control`), `top_k` and `metadata` are
  accepted and not sent; the reply carries no thinking blocks.
- Tools Anthropic runs itself (web search, code execution, computer use) are
  refused with `400`; Claude Code's own client-defined tools work.
- `POST /v1/messages/count_tokens` is an estimate, not the provider's count.

Claude Code can also call the workspace's governed tools: SOIT is an MCP server
too, see [`docs/mcp.md`](../../docs/mcp.md).
