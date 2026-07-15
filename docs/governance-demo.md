# SOIT Governance Demo

This runbook verifies the Phase 1.5 governance story in a 20-minute local demo:

1. Permissions: show workspace-scoped Agent bindings under the Owner role.
2. Secrets: show managed secret inventory used by governed tools and connectors.
3. Call audit: open Audit Explorer for policy-gateway request and response evidence.
4. Cost attribution: inspect run-level cost entries.
5. Replay: open the run detail with steps, tool calls, citations, audits, child runs, and costs.
6. Regression: show deterministic replay as the Agent publish gate.

Run the verifier from `soit/server`:

```powershell
uv run python scripts/verify_governance_demo.py --json-output ../docs/deployment/governance-demo-report.example.json
```

The command seeds deterministic demo data, runs the support-ticket regression evaluator, and writes a machine-readable report. A passing report has:

- `scenario`: `governance_demo_20_min`
- `passed`: `true`
- `summary.demo_minutes`: `20` or less
- evidence sections for `permissions`, `secrets`, `call_audit`, `cost_attribution`, `replay`, and `regression`

The primary UI routes for the demo are:

- `/agents`
- `/settings/secrets`
- `/observe/audits?gateway_type=tool`
- `/observe/runs/{run_id}`
