# Approvals

A tool whose policy requires approval does not run until someone decides. The
call stops, an approval request records what it would do, and the run waits:
an agent run until its turn resumes, a workflow run until it is resumed, a
[direct call or MCP call](gateway.md#calling-tools) until the caller sends it
again. Requests are listed under **Govern › Approvals** and served by
`/api/v1/observe/approvals`.

## Asking for approval

A ToolSpec asks for approval in its policy:

```json
"policy": {
  "audit_level": "basic",
  "approval": {
    "mode": "required",
    "risk_level": "high",
    "approvers": {"users": ["<finance lead user id>"], "roles": ["Admin"]},
    "timeout_seconds": 3600
  }
}
```

| Field | Meaning |
| --- | --- |
| `mode` | `required` stops every call for a decision; `none` never does. |
| `risk_level` | `low`, `normal`, `high` or `critical`, shown with the request. |
| `approvers.users` | Members or service principals who may decide (optional). |
| `approvers.roles` | Workspace roles whose holders may decide: `Owner`, `Admin` or `Dev` (optional). |
| `timeout_seconds` | How long a request stays open, 60 seconds to 30 days (optional). |

A request can also be opened directly with `POST /api/v1/observe/approvals`,
which takes the same `assignee_user_ids`, `assignee_roles` and an `expires_at`
in the future.

## Who decides

- A request with no approvers is decided by any member who can write: an
  Owner, Admin or Dev.
- A request with approvers is decided only by an assigned member, or by a
  member who holds an assigned role **when deciding**. A member removed from
  the workspace, or no longer holding the role, can no longer decide; anyone
  else is answered `403`.
- The requester and the workspace's Owners and Admins may cancel a request
  they cannot decide.
- The same rule holds wherever a decision is taken: the approvals page, a
  task's page, the API, or the chat client resuming an agent run.

`POST /api/v1/observe/approvals/{id}/resolve` takes `approved`, `rejected` or
`canceled` with an optional note. Exactly one decision is taken: sending the
same decision again returns the request unchanged, and a different decision on
a closed request answers `409`.

## Delegation

An approver who cannot decide can hand the request on:

```bash
curl -X POST "$SOIT_URL/api/v1/observe/approvals/$APPROVAL_ID/delegate" \
  -H "Authorization: Bearer $SOIT_TOKEN" -H "Content-Type: application/json" \
  -d '{"user_id": "<deputy user id>", "note": "Out this week"}'
```

The target must be a current member who can decide (an Owner, Admin or Dev),
and becomes the request's only approver; the person who delegated it can no
longer decide it.

## Deadlines and expiry

A request with an `expires_at` that nobody decided by then expires: the
approval sweeper closes it as `expired`. An expired request counts as a
rejection everywhere, so the call it asked about never runs. Deciding or
delegating a request past its deadline answers `409` and closes it as expired.
Nothing ever approves a request on its own.

The sweeper also closes, as `canceled`, the pending requests of runs that
ended before anyone decided, for example because their task was canceled. It
runs on the API service when `APPROVAL_SWEEPER_ENABLED=true` (on in the
shipped compose files), every `APPROVAL_SWEEPER_INTERVAL` seconds (30 by
default).

## What a decision does

| Decision | Agent run | Workflow run | Direct or MCP call |
| --- | --- | --- | --- |
| `approved` | The turn resumes and the call runs once. | Resuming the run runs the call once. | Sending the call again runs it once. |
| `rejected`, `canceled`, `expired` | The turn resumes and records the call as refused. | Resuming the run fails the node as `APPROVAL_REJECTED` without calling the tool. | Sending the call again reports it rejected. |
| still `pending` | The run keeps waiting. | Resuming answers `409`. | Sending the call again answers `202`. |

A task waiting on such a request without a paused agent turn, a workflow's
for example, fails with `approval_rejected`, `approval_canceled` or
`approval_expired`.

## History

`GET /api/v1/observe/approvals/{id}/decisions` returns every decision,
closing and delegation of a request in order: the action, who took it and
their role at the time (`system` for the sweeper), the note, and the approvers
before and after. Entries are only ever added.

## Not covered yet

- Approval requests do not notify anyone; reviewers find them under
  **Govern › Approvals**.
- A decision on a workflow request does not resume the run on its own; resume
  it through `POST /api/v1/workflows/{id}/runs/{run_id}/resume` or the console.
- Escalation to other approvers when a deadline passes, approval policies that
  assign requests by rule, and multi-step or quorum approvals are outside
  Community.
