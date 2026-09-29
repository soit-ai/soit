# Egress Policy Examples

SOIT refuses outbound calls by default. This page shows the policy shapes that
cover the common scenarios, each with the blast radius of getting it wrong,
and what a refused call looks like in the run evidence. Every field and
endpoint here comes from `server/app/kernel/security/egress.py`, the settings
in `server/app/settings/settings.py` and the routes under
`/api/v1/security`; nothing is illustrative.

## What the policy governs

Every outbound HTTP(S) call the runtime makes on a workspace's behalf goes
through the same guard: model providers (recorded as
`model-provider:<slug>`), the HTTP tool adapter, MCP servers and the OAuth
authorization servers that protect them, plugin HTTP runtimes, the governed
fetch used for attachments and ingestion, notification delivery, and any tool
call whose parameters carry a `url`, `endpoint` or `uri`, which the tool
policy gateway checks before the tool runs. Business code never opens a raw
client, so there is no second path around the policy.

## How a target is evaluated

The target is reduced to `scheme://host[:port]`; only the host name is
matched, case-insensitively. The port and the path play no part in the
decision. Then, in order:

1. The scheme must be `http` or `https` (notification delivery also accepts
   the schemes of its own channels, pinned to their fixed hosts), and a URL
   with embedded credentials (`https://user:pass@host`) is refused. These two
   checks run whether or not the policy is enabled.
2. With `ENABLE_EGRESS_POLICY=true`: a host that is `localhost` or an IP
   literal in a loopback, private or link-local range is refused unless it
   lies in `EGRESS_PRIVATE_NETWORKS`. Next, a match on the tenant blocklist,
   the workspace blocklist or the deployment blocklist refuses the call.
   Next, a match on the tenant allowlist, the workspace allowlist or the
   deployment allowlist allows it. Anything else is refused as
   `not_allowlisted`, including the case where every list is empty.
3. Always: the host name is resolved, and every address it resolves to must
   be public or lie in `EGRESS_PRIVATE_NETWORKS`; otherwise the call is
   refused as `non_public_address`. A name that resolves partly outside an
   opened network is refused.

List entries are host names, optionally with `*` wildcards: `*.example.com`
matches `api.example.com` but not `example.com` itself, so list both when
both are needed. Allowlists are additive across the three scopes; a blocklist
entry at any scope wins over every allowlist.

## Where the lists live

| Scope | Where | Who may change it |
| --- | --- | --- |
| Deployment | `ENABLE_EGRESS_POLICY`, `EGRESS_ALLOWLIST`, `EGRESS_BLOCKLIST` and `EGRESS_PRIVATE_NETWORKS` in `.env` (JSON arrays); a restart applies them. | The operator. |
| Tenant | `GET` / `PUT /api/v1/security/egress/tenant` with `{"allowlist": [...], "blocklist": [...]}`. | Tenant admins. |
| Workspace | `GET` / `PUT /api/v1/security/egress/workspace` with the same body; in the console, Govern > Policies > Edit rules. | Workspace Owner or Admin, not the Dev role. |

A `PUT` replaces both lists of that scope. Every save appends a policy
revision: `GET /api/v1/security/policies/revisions?scope=workspace` lists
them, `GET /api/v1/security/policies/bundle?scope=workspace` returns the
content-derived `bundle_id` of the policy in force, and
`POST /api/v1/security/policies/revisions/{revision_id}/rollback` puts an
earlier revision back as a new revision.

The `curl` examples below assume a signed-in session:

```bash
LOGIN=$(curl -s -X POST http://localhost:9200/api/v1/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"changeme123"}')
TOKEN=$(printf '%s' "$LOGIN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["access_token"])')
WORKSPACE=$(printf '%s' "$LOGIN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["workspace_id"])')
```

## Example 1: deny-all baseline

The state a fresh deployment is in. Nothing leaves the runtime until a host
is named somewhere.

```dotenv
ENABLE_EGRESS_POLICY=true
EGRESS_ALLOWLIST=[]
EGRESS_BLOCKLIST=[]
EGRESS_PRIVATE_NETWORKS=[]
```

with empty tenant and workspace lists:

```bash
curl -X PUT http://localhost:9200/api/v1/security/egress/workspace \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WORKSPACE" \
  -H 'Content-Type: application/json' \
  -d '{"allowlist": [], "blocklist": []}'
```

When to use it: as the starting point of a hardened deployment, adding hosts
one at a time as each is justified, and as the state to return to when a
workspace's policy is in doubt.

Blast radius: every governed outbound call is refused, including calls to
model providers, so chat, agents and workflows fail with the `403` shown
below until something is allowlisted. Each refusal is recorded, so the
evidence of what a workspace tried to reach accumulates from the first
minute.

## Example 2: known SaaS APIs only

Name the model providers everyone uses at the deployment level, and let a
workspace add the one SaaS API its tools call.

```dotenv
ENABLE_EGRESS_POLICY=true
EGRESS_ALLOWLIST=["api.openai.com","api.anthropic.com"]
EGRESS_BLOCKLIST=[]
```

```bash
curl -X PUT http://localhost:9200/api/v1/security/egress/workspace \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WORKSPACE" \
  -H 'Content-Type: application/json' \
  -d '{"allowlist": ["api.github.com"], "blocklist": []}'
```

A SaaS with per-region or per-tenant host names takes a wildcard, for
example `"*.openai.azure.com"`; keep the wildcard as narrow as the service
allows.

When to use it: production workspaces whose agents call a known set of
public APIs.

Blast radius: this workspace's agents reach the two providers and
`api.github.com`; every other host, and every private address, is refused.
Other workspaces reach the providers only. A wildcard such as `*.com` would
open the deployment to nearly everything, so review wildcards in the
revision history like any other change.

## Example 3: a model server on a private network

Outbound calls to private, loopback and link-local addresses are refused
regardless of the lists, which keeps out a local Ollama or an on-premises
vLLM as much as it keeps out the cloud metadata endpoint. Open the one
network the server lives in, and allowlist the server:

```dotenv
ENABLE_EGRESS_POLICY=true
EGRESS_ALLOWLIST=["api.openai.com"]
EGRESS_PRIVATE_NETWORKS=["10.20.0.0/16"]
```

```bash
curl -X PUT http://localhost:9200/api/v1/security/egress/workspace \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WORKSPACE" \
  -H 'Content-Type: application/json' \
  -d '{"allowlist": ["vllm.internal"], "blocklist": []}'
```

Then register the provider in ModelHub with the base URL
`http://vllm.internal:8000/v1`. Both conditions are needed: an opened
network without an allowlist entry, or an allowlist entry without the
network, is still refused.

Two variations:

- A server on the same machine as a non-containerised API is reached as
  `localhost` or `127.0.0.1`. `localhost` needs both loopback networks,
  `["127.0.0.1/32", "::1/128"]`, since the name resolves to both; an
  allowlist entry of `127.0.0.1` needs only the first.
- A server on the Docker host, reached from the Compose stack as
  `host.docker.internal`, resolves to the host-gateway address of the Docker
  network. Find it with
  `docker compose --env-file .env -f docker/docker-compose.yml exec api python -c "import socket; print(socket.gethostbyname('host.docker.internal'))"`,
  open that address (`/32`) and allowlist `host.docker.internal`.

When to use it: model servers, MCP servers or tools that run inside your
own network.

Blast radius: every governed caller in the deployment may reach any address
in the opened network that is also allowlisted, from any workspace. Open the
smallest network that contains the server, never a whole private range you
do not control, and never link-local space: `169.254.169.254` stays refused
only while `169.254.0.0/16` stays closed. The settings refuse `0.0.0.0/0`
and `::/0` at startup.

## Example 4: one workspace narrowed to one host

Allowlists add up across scopes, so a workspace cannot be narrowed by giving
it a shorter allowlist than its tenant. It is narrowed with its blocklist,
which beats every allowlist.

Tenant policy, set by a tenant admin:

```bash
curl -X PUT http://localhost:9200/api/v1/security/egress/tenant \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WORKSPACE" \
  -H 'Content-Type: application/json' \
  -d '{"allowlist": ["api.openai.com", "*.tools.example.com"], "blocklist": []}'
```

The sandbox workspace, set by its Owner or Admin:

```bash
curl -X PUT http://localhost:9200/api/v1/security/egress/workspace \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $SANDBOX" \
  -H 'Content-Type: application/json' \
  -d '{"allowlist": [], "blocklist": ["*.tools.example.com"]}'
```

Agents in the sandbox reach `api.openai.com` and nothing else; the other
workspaces of the tenant keep the internal tools.

When to use it: a workspace for evaluation, untrusted plugins or a customer
demo inside a tenant that otherwise reaches internal systems.

Blast radius: the sandbox only. Note the direction of the asymmetry: a
workspace's allowlist widens what its tenant allows, and only its Owner and
Admin roles can save it. Separation of duties is the control here, so keep
those roles with the people who are allowed to change policy.

## Example 5: a permissive profile for development

For a laptop where the point is to see whether an agent can complete a task
at all:

```dotenv
ENABLE_EGRESS_POLICY=false
EGRESS_PRIVATE_NETWORKS=["127.0.0.1/32","::1/128"]
```

Turning the policy off skips the list checks and the private-address check
of step 2 above. It does not skip step 1 or step 3: URLs with embedded
credentials and non-HTTP schemes are still refused, and a host that resolves
to a private address outside the opened networks is still refused. Without
the second line a local Ollama stays unreachable even with the policy off.

When to use it: local development and throwaway evaluation only.

Blast radius: every workspace may call any public host, and calls to public
hosts are neither refused nor recorded, so the evidence trail has a gap for
as long as the flag is off. The production validation does not refuse this
setting, so nothing but the `.env` review stands between a development
profile and a production deployment; keep the flag out of any `.env` that
is promoted.

## What the policy cannot express

The lists know hosts, not callers. The refusal records which caller was
refused (`resource_ref` such as `tool:http:demo`, `model-provider:openai`
or an MCP server reference), but the decision does not depend on it, so
there is no per-tool or per-agent egress rule. Scope which tools an agent
may call through the agent version's capability allowlist, scope which
credentials a tool may use through workspace secrets, and keep the egress
lists to the hosts the workspace as a whole may reach. Ports and paths are
not matched either: allowlisting a host allows every port and path on it.

## What a blocked call looks like

The caller gets `403` with the standard error envelope. The URL is reported
reduced to its origin, since the decision was made on the host:

```json
{
  "success": false,
  "code": "FORBIDDEN",
  "message": "Egress to evil.example is not allowed by policy",
  "details": {
    "url": "https://evil.example",
    "domain": "evil.example",
    "resource_ref": "tool:http:demo"
  },
  "request_id": "req_01J..."
}
```

The message names the reason: `is not allowed by policy` for
`not_allowlisted`, `is blocked by tenant policy` and
`is blocked by workspace policy` for a blocklist match,
`Outbound target resolves to a private or non-public address` for
`non_public_address`, and `Egress policy lookup failed; request denied` when
the scope policy could not be read (the policy fails closed).

In the run, the tool step ends `failed` before the tool is invoked: the
step's `metrics_json.tool_call` shows `"status": "failed"` with the
arguments the agent supplied, and the step's audit entry carries the full
URL and `ForbiddenError`. A URL injected from a secret is reported by the
secret's reference instead, so a refusal never writes a secret into the
evidence.

Independently of the run, every refusal writes an audit event of type
`security.egress.blocked` (`resource_type` `egress`, `resource_id` the host,
`outcome` `denied`) whose payload is:

```json
{
  "resource_ref": "tool:http:demo",
  "url": "https://evil.example",
  "domain": "evil.example",
  "reason": "not_allowlisted",
  "tenant_bundle_id": "bundle_...",
  "workspace_bundle_id": "bundle_..."
}
```

The two bundle identifiers name the exact policy content that refused the
call, so the refusal can be read against the rules that were in force even
after the policy has moved on. In a content-free workspace the URL is
reduced to its origin before it is stored.

`GET /api/v1/security/egress/blocks` summarises the refusals inside a
window, counted from those same records:

```bash
curl "http://localhost:9200/api/v1/security/egress/blocks?since=2026-09-28T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WORKSPACE"
```

```json
{
  "since": "2026-09-28T00:00:00Z",
  "until": null,
  "total": 3,
  "subjects": 1,
  "domains": 2,
  "recent": [
    {
      "id": "aud_01J...",
      "domain": "evil.example",
      "resource_ref": "tool:http:demo",
      "reason": "not_allowlisted",
      "url": "https://evil.example",
      "actor_user_id": "usr_01J...",
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "created_at": "2026-09-28T09:14:02Z",
      "tenant_bundle_id": "bundle_...",
      "workspace_bundle_id": "bundle_..."
    }
  ]
}
```

`subjects` counts distinct callers, which is what the console's Govern >
Policies header means by "1 caller" next to its egress block count for the
last 24 hours. `GET /api/v1/security/egress/audits` is a different list:
it records changes to the policy itself, not calls the policy refused.
