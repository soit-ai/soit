# SOIT as an MCP server

SOIT serves each workspace's tools to MCP clients (Claude Code, Cursor, the
official SDKs and any other client of the streamable HTTP transport) at
`/mcp`. A client connects with a SOIT API key; the tools it is offered are the
ones that key may invoke, and every call it makes is a governed run in SOIT,
the same as a call through [`/api/v1/tools`](gateway.md#calling-tools).

Client setup for Claude Code, Cursor and Python is in
[`examples/mcp/`](../examples/mcp/).

## Connecting

| Setting | Value |
| ------- | ----- |
| URL | the API address plus `/mcp`, e.g. `https://soit.example.com/mcp` |
| Transport | streamable HTTP |
| Credential | `Authorization: Bearer sk_…`, a SOIT API key |

The key names the workspace. A signed-in session works too, with the
workspace in `X-Workspace-Id`. Listing and calling tools take a credential
that may write in the workspace (a Dev, Admin or Owner, and a key with the
`write` scope); a read-only credential is offered no tools.

## Stateless

The endpoint implements the stateless form of the transport, as the current
MCP revisions (up to `2025-11-25`) allow:

- Every `POST /mcp` carries one JSON-RPC message and is answered on its own,
  with `application/json`. No `Mcp-Session-Id` is issued and none is needed,
  so any API instance can answer any request.
- `GET /mcp` (a server-to-client stream) and `DELETE /mcp` (ending a session)
  answer `405`: the server sends no notifications and makes no requests of the
  client.
- `initialize` negotiates the protocol version: the client's, when supported,
  otherwise the newest SOIT supports. A request whose `MCP-Protocol-Version`
  header names an unsupported version is refused with `400`.
- Notifications are accepted with `202`; batches are refused.

## Tools

`tools/list` offers every tool of the workspace the credential may invoke:
built-ins, installed plugin tools and the tools of enabled MCP servers. A key
with **Allowed tools** set sees only those.

MCP clients and model APIs accept only letters, digits, `_` and `-` in a tool
name, so each SOIT ref is given a name: `tool:function:time_now` becomes
`function_time_now`, `mcp_tool:github:create_issue` becomes
`github_create_issue`. A name that would collide with another, or run past 64
characters, carries a short digest of its ref. Each tool's `_meta` holds its
ref as `ai.soit/tool_ref`.

`tools/call` runs the tool through the tool gateway SOIT's agents use: secrets,
egress policy, rate limits, budgets, audit and cost apply, and the call is a
run with `mode=tool` whose id comes back in the result's `_meta` as
`ai.soit/run_id`. A result that is a JSON object is also returned as
`structuredContent`.

Refusals the model can act on (arguments that do not match the tool's
schema, a blocked address, a spent budget) come back as a tool result with
`isError: true` and the reason, so the model can correct itself. An unknown
tool name is the protocol error `-32602`.

## Approval

A tool whose policy requires approval does not run on the first call. The
result is an error that says so, with the approval id (`ai.soit/approval_id`)
and run id, and the request appears in **Govern › Approvals**. Once a reviewer
decides, the same call with the same arguments runs the tool, or reports the
rejection. Calling again before the decision returns the same pending
approval; arguments that differ make a new call, with a new approval.

## Authorization

A request without a working credential is answered `401` with a challenge
that names the endpoint's OAuth 2.1 protected resource metadata (RFC 9728):

```
WWW-Authenticate: Bearer resource_metadata="https://soit.example.com/.well-known/oauth-protected-resource/mcp"
```

The metadata, also served at `/.well-known/oauth-protected-resource`, names
the resource and that bearer tokens go in the `Authorization` header. SOIT
authenticates MCP clients with its API keys, which clients send as a
configured header. A deployment that puts an OAuth authorization server in
front of SOIT lists it in `MCP_AUTHORIZATION_SERVERS`, and the metadata
publishes it for clients that discover their authorization that way.

## Deployment settings

| Setting | Purpose |
| ------- | ------- |
| `MCP_RESOURCE_URL` | The endpoint's public URL, named in the metadata and the challenge. Empty derives it from the request; behind a proxy that rewrites the host, set it. The production compose file sets it from `SOIT_PUBLIC_HOSTNAME`. |
| `MCP_AUTHORIZATION_SERVERS` | OAuth authorization servers to publish, as a JSON list. |
| `MCP_ALLOWED_ORIGINS` | Browser origins, besides the endpoint's own, that may call it. A request from any other `Origin` is refused with `403`, which keeps a web page from reaching the endpoint through a user's browser. Clients that are not browsers send no `Origin`. |

The production gateway (`docker/production/Caddyfile`) routes `/mcp` and the
metadata paths to the API.

## Known limitations

- Only tools are served: no resources, prompts, sampling or elicitation.
- The tool list is read when asked; the server sends no `list_changed`
  notification when tools are installed or removed.
- A call that needs approval runs only when the client calls again; nothing
  runs it on the client's behalf.
- Tool results are returned whole; there are no progress notifications.
