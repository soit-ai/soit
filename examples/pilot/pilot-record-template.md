# Pilot record

Copy this file for each pilot and fill it in as you go. It is the evidence a
pilot is judged on: what was connected, how long it took, what failed and
why, and what the acceptance run showed. Keep secrets, keys and customer data
out of it; refer to them by name.

## Scope

| Item | Value |
| --- | --- |
| Organisation | |
| Scenario | gateway: model calls, limits, failover, cost check, evidence |
| Applications connected (two at most) | |
| Models and providers | |
| Acceptance owner on the customer side | |
| Support scope agreed | e.g. business hours, named contact, response time |
| SOIT version and deployment | e.g. v1.5.1, compose on one VM |

## Timeline

| Milestone | Date and time | Elapsed |
| --- | --- | --- |
| Kick-off | | |
| SOIT reachable at its URL (`/health/ready` green) | | |
| First governed call from the customer's application | | **onboarding time** (target: one working day) |
| Acceptance run passed (`pilot_acceptance.py check`) | | |
| First provider bill compared with the ledger | | |
| Upgrade rehearsed (backup, upgrade, verify) | | **upgrade time** |
| Restore rehearsed (from backup to green) | | **restore time** |
| Pilot accepted or ended | | |

## Failures and their causes

One row per problem that stopped or slowed the pilot, however small.

| When | Symptom | Cause | Fix | Time lost |
| --- | --- | --- | --- | --- |
| | | | | |

## Effort

| Who | Task | Person-days |
| --- | --- | --- |
| | setup | |
| | integration support | |
| | acceptance and reporting | |
| | **total** (target: ten at most for a repeat pilot) | |

## Acceptance

Attach the report `pilot_acceptance.py check` wrote (`pilot-report.json` and
`pilot-report.md`), and note each check that was skipped and why.

| Check | Result | Notes |
| --- | --- | --- |
| Allowed call answered, run recorded, cost priced | | |
| Invalid key refused (401) | | |
| Model outside the key's list refused (403) | | |
| Budget exhausted refused (402) | | |
| Failover to the next target recorded as an attempt | | |
| Unpriced call refused under the workspace policy (403) | | |
| Repeated tool call with one idempotency key runs once | | |
| Cost reconciliation: priced totals per currency, nothing unpriced | | |
| Evidence bundle downloaded and its SHA-256 matches | | |

## Cost check against the provider's bill

| Provider | Window | Provider bill | SOIT ledger | Difference | Explained by |
| --- | --- | --- | --- | --- | --- |
| | | | | | price version, cache or batch pricing, estimated usage, time zone, late settlement, unrecorded call |

## Outcome

- Decision (continue, buy, stop) and who made it:
- What would have to change for the next pilot:
