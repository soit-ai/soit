# Security API

This document covers security-related APIs under the `/api/v1/security` prefix.

## Egress policy

Endpoints:
- `GET /egress/tenant`: read tenant-level egress policy (tenant admin only)
- `PUT /egress/tenant`: update tenant-level egress policy (tenant admin only)
- `GET /egress/workspace`: read workspace-level egress policy (workspace read)
- `PUT /egress/workspace`: update workspace-level egress policy (workspace write)
- `GET /egress/audits`: list policy change audits (workspace read)

Request/response schema:
- `EgressPolicyUpdate`: `{ allowlist: string[], blocklist: string[] }`
- `EgressPolicyResponse`: `{ scope: "tenant"|"workspace", allowlist: string[], blocklist: string[] }`
- `EgressPolicyAuditResponse`: includes `scope`, `allowlist`, `blocklist`, and audit metadata

Notes:
- Policies are deny-by-default when enabled. Tenant policy applies before workspace policy.
- Egress audits are written on policy updates and can be paginated with `page_token`.

## Usage limits (rate limits + quotas)

Endpoints:
- `GET /limits/tenant`: read tenant-level limits (tenant admin only)
- `PUT /limits/tenant`: update tenant-level limits (tenant admin only)
- `GET /limits/workspace`: read workspace-level limits (workspace read)
- `PUT /limits/workspace`: update workspace-level limits (workspace write)

Request/response schema:
- `UsagePolicyUpdate`:
  - `llm_rate_limit_per_minute`: optional integer (>= 1)
  - `tool_rate_limit_per_minute`: optional integer (>= 1)
  - `llm_daily_quota`: optional integer (>= 1)
  - `tool_daily_quota`: optional integer (>= 1)
- `UsagePolicyResponse`: includes the same fields plus `scope`

Example:

```json
PUT /api/v1/security/limits/tenant
{
  "llm_rate_limit_per_minute": 120,
  "tool_rate_limit_per_minute": 60,
  "llm_daily_quota": 10000,
  "tool_daily_quota": 5000
}
```

## Migration

The following migration adds the new usage limit columns:
- `app/alembic/versions/20260123001000_security_limits.py`

Apply with:
- `uv run alembic upgrade head`
