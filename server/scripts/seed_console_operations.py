"""Operational history for the console prototype seed.

``seed_console_prototype`` plants the objects the prototype draws -- agents,
workflows, knowledge bases, runs. A console reviewed against that alone still
shows empty panels wherever the screen reads history rather than objects:
schedules, task timelines, decided approvals, notifications, grants, policy
revisions, ingest queues, draft reviews, releases, dead letters, workflow runs
and the per-user shortcuts. This module seeds those, linked to the prototype's
objects, so every list and tile has rows in each state it can render.

It is called from ``seed_console_prototype`` and shares its id infix, so that
script's ``--reset`` clears these rows too.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunStep
from app.kernel.runtime.db.models.schedules import Schedule
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.security.policy_bundle import policy_bundle_id
from app.modules.agent.domain.models import AgentPublish, AgentVersion
from app.modules.evaluation.domain.models import RegressionReport
from app.modules.feedback.domain.models import ProductFeedback
from app.modules.identity.domain.models import (
    PinnedObject,
    ResourceGrant,
    SavedView,
    User,
    Workspace,
)
from app.modules.knowledge.domain.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestTask,
)
from app.modules.notification.domain.models import Notification, NotificationEndpoint
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.secrets.domain.models import Secret
from app.modules.security.application.schemas import PolicyDocument
from app.modules.security.domain.models import PolicyRevision
from app.modules.workflow.domain.models import WorkflowRun
from scripts.seed_console_prototype import (
    AGENTS,
    KNOWLEDGE,
    RUNS,
    SEED_SOURCE,
    TASKS,
    TEAMMATES,
    TRACE_PREFIX,
    WORKFLOWS,
    _meta,
    _seed_tool_call,
    _sid,
    _upsert,
)

#: Children before parents, for ``--reset``.
RESET_MODELS: tuple[type[Any], ...] = (
    TaskCheckpoint,
    TaskEvent,
    KnowledgeChunk,
    KnowledgeIngestTask,
    WorkflowRun,
    AgentPublish,
    Schedule,
    Notification,
    NotificationEndpoint,
    PinnedObject,
    SavedView,
    ResourceGrant,
    PolicyRevision,
    ProductFeedback,
    RegressionReport,
    RunArtifact,
    Secret,
)


def _ids(ctx: RequestContext, prefix: str, specs: list[dict[str, Any]]) -> dict[str, str]:
    return {spec["key"]: _sid(prefix, ctx, spec["key"]) for spec in specs}


# --------------------------------------------------------------------------- #
# workflow runs -- workflows.html, workflow detail
# --------------------------------------------------------------------------- #

#: (status, age in hours) per run, newest first. Every published workflow gets
#: the same mix so each row shows a success rate below 100% and a last run;
#: the 3h failure usually lands inside the workbench's UTC "today".
WORKFLOW_RUN_MIX: list[tuple[str, int]] = [
    ("succeeded", 1),
    ("failed", 3),
    ("succeeded", 7),
    ("failed", 19),
    ("succeeded", 30),
    ("succeeded", 52),
    ("succeeded", 75),
    ("succeeded", 110),
    ("succeeded", 150),
]


async def _seed_workflow_runs(db: AsyncSession, ctx: RequestContext) -> dict[str, list[str]]:
    now = utc_now()
    workflow_ids = _ids(ctx, "wf", WORKFLOWS)
    runs_by_workflow: dict[str, list[str]] = {}
    for spec in WORKFLOWS:
        if not spec["published"]:
            continue
        key = spec["key"]
        workflow_id = workflow_ids[key]
        nodes = int(spec["nodes"])
        runs_by_workflow[key] = []
        for index, (status, hours_ago) in enumerate(WORKFLOW_RUN_MIX):
            suffix = f"wf:{key}:{index}"
            run_id = _sid("run", ctx, suffix)
            started = now - timedelta(hours=hours_ago, minutes=index * 3)
            duration_ms = 4_000 + nodes * 900 + index * 350
            ended = started + timedelta(milliseconds=duration_ms)
            failed = status == "failed"
            await _upsert(
                db,
                Run,
                run_id,
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "user_id": ctx.user_id,
                    "trace_id": f"{TRACE_PREFIX}{suffix}",
                    "mode": "workflow",
                    "kind": "schedule" if index % 2 else "api",
                    "subject_kind": "workflow",
                    "subject_id": workflow_id,
                    "subject_version_id": _sid("wfv", ctx, key),
                    "status": status,
                    "input_summary": f"{key} · run {index + 1}",
                    "output_summary": "" if failed else f"{key} completed",
                    "started_at": started,
                    "ended_at": ended,
                    "duration_ms": duration_ms,
                    "created_at": started,
                    "error_code": "node_failed" if failed else None,
                    "error_message": (
                        "Node post-results timed out after 3 attempts." if failed else None
                    ),
                },
            )
            completed = nodes - 1 if failed else nodes
            for order in range(3):
                step_key = f"{suffix}:{order}"
                step_row_id = _sid("step", ctx, step_key)
                step_type = ("agent_plan", "retrieval", "tool")[order]
                step_failed = failed and order == 2
                await _upsert(
                    db,
                    RunStep,
                    step_row_id,
                    {
                        "tenant_id": ctx.tenant_id,
                        "workspace_id": ctx.workspace_id,
                        "run_id": run_id,
                        "step_id": f"node-{order}",
                        "step_type": step_type,
                        "status": "failed" if step_failed else "succeeded",
                        "started_at": started,
                        "ended_at": ended,
                        "metrics_json": _meta(latency_ms=duration_ms // 3),
                    },
                )
                if step_type == "tool":
                    await _seed_tool_call(
                        db,
                        ctx,
                        run_id=run_id,
                        step_row_id=step_row_id,
                        key=step_key,
                        index=index,
                        failed=step_failed,
                        started=started,
                        ended=ended,
                        latency_ms=duration_ms // 3,
                    )
            await _upsert(
                db,
                WorkflowRun,
                _sid("wfr", ctx, suffix),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "run_id": run_id,
                    "workflow_id": workflow_id,
                    "status": status,
                    "total_nodes": nodes,
                    "completed_nodes": completed,
                    "failed_nodes": 1 if failed else 0,
                    "waiting_nodes": 0,
                    "checkpoint_json": _meta(last_node=f"node-{completed}"),
                    "inputs_json": {"trigger": "schedule" if index % 2 else "api"},
                    "request_context_json": {"user_id": ctx.user_id},
                    "created_at": started,
                    "updated_at": ended,
                },
            )
            runs_by_workflow[key].append(run_id)
    await db.commit()
    return runs_by_workflow


# --------------------------------------------------------------------------- #
# schedules -- schedules.html
# --------------------------------------------------------------------------- #

#: (name, target kind, target key, cron, enabled, last status, last error)
SCHEDULES: list[tuple[str, str, str, str, bool, str | None, str | None]] = [
    ("nightly-docs-sync", "workflow", "docs-nightly-sync", "0 2 * * *", True, "succeeded", None),
    ("weekly-release-digest", "workflow", "release-digest", "0 9 * * 1", True, "succeeded", None),
    (
        "hourly-billing-audit",
        "agent",
        "billing-audit",
        "0 * * * *",
        True,
        "failed",
        "Egress destination not in the workspace allowlist.",
    ),
    ("monthly-invoice-close", "workflow", "invoice-reconcile", "0 6 1 * *", True, None, None),
    ("quota-sweep", "agent", "quota-sentinel", "*/15 * * * *", False, "succeeded", None),
]


async def _seed_schedules(
    db: AsyncSession, ctx: RequestContext, workflow_runs: dict[str, list[str]]
) -> list[str]:
    now = utc_now()
    agent_ids = _ids(ctx, "agt", AGENTS)
    workflow_ids = _ids(ctx, "wf", WORKFLOWS)
    ids: list[str] = []
    for index, (name, kind, target, cron, enabled, last_status, last_error) in enumerate(
        SCHEDULES
    ):
        schedule_id = _sid("sch", ctx, name)
        target_id = workflow_ids[target] if kind == "workflow" else agent_ids[target]
        fired = last_status is not None
        last_run_id = (workflow_runs.get(target) or [None])[0] if kind == "workflow" else None
        await _upsert(
            db,
            Schedule,
            schedule_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": name,
                "description": f"{target} on {cron}",
                "target_kind": kind,
                "target_id": target_id,
                "input_json": {"source": SEED_SOURCE},
                "cron": cron,
                "timezone": "UTC",
                "catch_up": index == 0,
                "enabled": enabled,
                # Always in the future, so a running schedule worker never
                # fires a seeded schedule by surprise.
                "next_fire_at": (now + timedelta(hours=index + 1)) if enabled else None,
                "last_fired_at": (now - timedelta(hours=index + 1)) if fired else None,
                "last_run_id": last_run_id,
                "last_status": last_status,
                "last_error": last_error,
                "created_by": ctx.user_id,
                "created_at": now - timedelta(days=30 - index),
            },
        )
        ids.append(schedule_id)
    await db.commit()
    return ids


# --------------------------------------------------------------------------- #
# task timelines and approvals -- tasks.html, approvals.html
# --------------------------------------------------------------------------- #


async def _seed_task_history(db: AsyncSession, ctx: RequestContext, run_ids: list[str]) -> None:
    now = utc_now()
    for offset, (name, _note, _type, status, done, total) in enumerate(TASKS):
        task_id = _sid("task", ctx, name)
        created = now - timedelta(minutes=9 * (offset + 1) + 2)
        run_id = run_ids[offset % len(run_ids)] if run_ids and status != "queued" else None
        task = await db.get(Task, task_id)
        if task is not None:
            # The task detail's linked-runs panel reads this column.
            task.run_id = run_id
            db.add(task)
        timeline: list[tuple[str, dict[str, Any]]] = [("task.created", {"status": "queued"})]
        if status != "queued":
            timeline.append(("task.status", {"status": "running", "run_id": run_id}))
        checkpoints = min(done, 4) if status != "queued" else 0
        for number in range(1, checkpoints + 1):
            timeline.append(("task.checkpoint", {"checkpoint_no": number, "status": "saved"}))
        if status == "failed":
            timeline.append(("task.retry", {"status": "running", "attempt": 2}))
            timeline.append(
                (
                    "task.status",
                    {"status": "failed", "error_code": "step_failed", "run_id": run_id},
                )
            )
        elif status in {"succeeded", "waiting_approval"}:
            timeline.append(("task.status", {"status": status, "run_id": run_id}))
        for order, (event_type, payload) in enumerate(timeline):
            await _upsert(
                db,
                TaskEvent,
                _sid("tev", ctx, f"{name}:{order}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "task_id": task_id,
                    "event_type": event_type,
                    "payload_json": payload,
                    "created_at": created + timedelta(seconds=40 * order),
                },
            )
        for number in range(1, checkpoints + 1):
            await _upsert(
                db,
                TaskCheckpoint,
                _sid("tck", ctx, f"{name}:{number}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "task_id": task_id,
                    "checkpoint_no": number,
                    "status": "saved",
                    "payload_json": {"completed": round(done * number / checkpoints), "total": total},
                    "created_at": created + timedelta(minutes=number),
                },
            )
    await db.commit()


#: (title, policy ref, agent key, status, hours ago, note). The pending pair is
#: seeded by the prototype script; these fill the Decided tab and its tiles.
DECIDED_APPROVALS: list[tuple[str, str, str, str, int, str]] = [
    ("Restart checkout-api pods", "infra.restart.prod", "ops-copilot", "approved", 3, "within change window"),
    ("Refund order #88213", "billing.refund", "support-triage", "approved", 11, "matches refund policy"),
    ("Purge CDN cache for /docs", "cdn.purge", "kb-refresher", "rejected", 26, "purge scheduled for tonight"),
    ("Post Q3 accrual adjustments", "finance.journal.post", "billing-audit", "expired", 50, "no reviewer in 24h"),
    ("Rotate SLACK_BOT_TOKEN", "secrets.rotate", "ops-copilot", "canceled", 70, "rotated manually"),
]


async def _seed_approval_history(db: AsyncSession, ctx: RequestContext, run_ids: list[str]) -> None:
    now = utc_now()
    agent_ids = _ids(ctx, "agt", AGENTS)
    waiting_task = _sid("task", ctx, "invoice-reconcile")
    # The prototype's pending approvals carry no task or run, so the task
    # detail rail (filtered by task) and the run links stayed empty.
    pending = [
        ("Post 14 journal entries to the ledger", "finance.journal.post", {"entries": 14, "ledger": "GL-4100"}),
        ("Scale checkout-api to 16 replicas", "infra.scale.prod", {"deployment": "checkout-api", "replicas": 16}),
    ]
    for index, (title, tool_ref, parameters) in enumerate(pending):
        approval = await db.get(ApprovalRequest, _sid("apr", ctx, title))
        if approval is None:
            continue
        approval.task_id = waiting_task if index == 0 else None
        approval.run_id = run_ids[index] if run_ids else None
        approval.details_json = _meta(tool_ref=tool_ref, parameters=parameters)
        db.add(approval)
    for index, (title, policy_ref, agent_key, status, hours_ago, note) in enumerate(
        DECIDED_APPROVALS
    ):
        created = now - timedelta(hours=hours_ago)
        await _upsert(
            db,
            ApprovalRequest,
            _sid("apr", ctx, title),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agent_ids.get(agent_key),
                "run_id": run_ids[(index + 3) % len(run_ids)] if run_ids else None,
                "title": title,
                "policy_ref": policy_ref,
                "status": status,
                "details_json": _meta(tool_ref=policy_ref, requested_by=agent_key),
                "requested_by": ctx.user_id,
                "resolved_by": None if status == "expired" else ctx.user_id,
                "resolution_note": note,
                "resolved_at": created + timedelta(minutes=12 + index * 17),
                "created_at": created,
            },
        )
    await db.commit()


# --------------------------------------------------------------------------- #
# notifications, shortcuts, grants, feedback -- per-user surfaces
# --------------------------------------------------------------------------- #

#: (type, severity, status, title, source module, route, minutes ago)
NOTIFICATIONS: list[tuple[str, str, str, str, str, str, int]] = [
    ("alert", "error", "unread", "billing-audit failed 3 runs in the last hour", "observe", "/observe/runs?status=failed", 6),
    ("message", "warning", "unread", "2 approvals are waiting on you", "approvals", "/govern/approvals", 18),
    ("reminder", "info", "unread", "SLACK_BOT_TOKEN rotation is due in 3 days", "secrets", "/govern/secrets", 45),
    ("system", "success", "unread", "product-docs finished re-indexing", "knowledge", "/build/knowledge", 90),
    ("alert", "warning", "read", "runbooks index is still building after 6h", "knowledge", "/build/knowledge", 240),
    ("custom", "info", "read", "support-triage v13 submitted for review", "agent", "/build/agents", 600),
    ("system", "info", "read", "Workspace egress policy updated to revision 4", "security", "/govern/policies", 1500),
    ("message", "success", "archived", "Credits topped up: 4,212.4 granted", "billing", "/settings/billing", 4000),
]

#: (name, kind, display target, secret key, status)
NOTIFICATION_ENDPOINTS: list[tuple[str, str, str, str, str]] = [
    ("on-call email", "email", "ops@acme.io", "SLACK_BOT_TOKEN", "active"),
    ("incident webhook", "webhook", "https://hooks.acme.io/soit", "helpdesk-api", "active"),
    ("#ops-alerts", "slack", "#ops-alerts", "SLACK_BOT_TOKEN", "disabled"),
]


async def _seed_notifications(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    for index, (kind, severity, status, title, module, route, minutes_ago) in enumerate(
        NOTIFICATIONS
    ):
        created = now - timedelta(minutes=minutes_ago)
        await _upsert(
            db,
            Notification,
            _sid("ntf", ctx, f"{ctx.user_id}:{index}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "user_id": ctx.user_id,
                "type": kind,
                "severity": severity,
                "status": status,
                "title": title,
                "content": f"{title}. Open the linked page for the evidence.",
                "source_module": module,
                "action": {"route": route},
                "meta": _meta(),
                "read_at": created + timedelta(minutes=5) if status != "unread" else None,
                "archived_at": created + timedelta(hours=1) if status == "archived" else None,
                "created_at": created,
                "updated_at": created,
            },
        )
    for name, kind, target, secret_key, status in NOTIFICATION_ENDPOINTS:
        await _upsert(
            db,
            NotificationEndpoint,
            _sid("nep", ctx, f"{ctx.user_id}:{name}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "user_id": ctx.user_id,
                "name": name,
                "kind": kind,
                "secret_id": _sid("sec", ctx, secret_key),
                "display_target": target,
                "status": status,
            },
        )
    await db.commit()


PINS: list[tuple[str, str, str]] = [
    ("agent", "ops-copilot", "agt"),
    ("workflow", "ticket-escalation", "wf"),
    ("knowledge", "product-docs", "knw"),
    ("task", "invoice-reconcile", "task"),
]

#: (surface, name, query, default)
SAVED_VIEWS: list[tuple[str, str, str, bool]] = [
    ("runs", "Failed only", "status=failed", True),
    ("runs", "Workflow runs", "mode=workflow", False),
    ("runs", "Tool calls", "has_tool_call=1", False),
    ("traces", "Last 7 days", "range=7d", False),
]


async def _seed_shortcuts(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    for index, (object_type, key, prefix) in enumerate(PINS):
        await _upsert(
            db,
            PinnedObject,
            _sid("pin", ctx, f"{ctx.user_id}:{object_type}:{key}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "user_id": ctx.user_id,
                "object_type": object_type,
                "object_id": _sid(prefix, ctx, key),
                "label": key,
                "created_at": now - timedelta(days=index + 1),
            },
        )
    for surface, name, query, is_default in SAVED_VIEWS:
        await _upsert(
            db,
            SavedView,
            _sid("view", ctx, f"{ctx.user_id}:{surface}:{name}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "user_id": ctx.user_id,
                "surface": surface,
                "name": name,
                "query": query,
                "is_default": is_default,
            },
        )
    await db.commit()


#: (teammate email, resource kind, resource key, actions)
GRANTS: list[tuple[str, str, str, list[str]]] = [
    ("ming@acme.io", "agent", "ops-copilot", ["read", "run"]),
    ("ming@acme.io", "workflow", "ticket-escalation", ["read", "run", "update"]),
    ("wei@acme.io", "workflow", "invoice-reconcile", ["read", "run", "update", "delete"]),
    ("dana@acme.io", "knowledge", "product-docs", ["read"]),
    ("dana@acme.io", "agent", "support-triage", ["read"]),
]

_GRANT_PREFIX = {"agent": "agt", "workflow": "wf", "knowledge": "knw"}


async def _seed_grants(db: AsyncSession, ctx: RequestContext) -> None:
    from sqlalchemy import select

    for email, kind, key, actions in GRANTS:
        user = (await db.exec(select(User).where(User.email == email))).scalars().first()
        if user is None:
            continue
        await _upsert(
            db,
            ResourceGrant,
            _sid("grant", ctx, f"{email}:{kind}:{key}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "resource_type": kind,
                "resource_id": _sid(_GRANT_PREFIX[kind], ctx, key),
                "user_id": user.id,
                "actions": actions,
                "created_by": ctx.user_id,
            },
        )
    await db.commit()


#: (title, category, priority, status, resolution note)
FEEDBACK: list[tuple[str, str, str, str, str | None]] = [
    ("Run detail should link the approval that paused it", "feature", "medium", "open", None),
    ("Knowledge upload silently fails without an index", "bug", "high", "in_progress", None),
    ("Traces list is slow past 5k spans", "performance", "medium", "resolved", "Paged the span query."),
    ("Approvals rail hides the tool parameters", "usability", "low", "closed", "Parameters now render in the rail."),
    ("Export the audit log as CSV", "other", "critical", "open", None),
]


async def _seed_feedback(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    for index, (title, category, priority, status, note) in enumerate(FEEDBACK):
        created = now - timedelta(days=index * 3 + 1)
        resolved = status in {"resolved", "closed"}
        await _upsert(
            db,
            ProductFeedback,
            _sid("fb", ctx, f"{ctx.user_id}:{title}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "title": title,
                "description": f"{title}. Seen while reviewing the console.",
                "category": category,
                "priority": priority,
                "status": status,
                "context_json": _meta(page="/"),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
                "resolved_by": ctx.user_id if resolved else None,
                "resolution_note": note,
                "resolved_at": created + timedelta(days=1) if resolved else None,
                "created_at": created,
            },
        )
    await db.commit()


# --------------------------------------------------------------------------- #
# policy revisions and egress audits -- policies.html, audit.html
# --------------------------------------------------------------------------- #

#: Each revision's egress rules, oldest first. The last one matches the
#: workspace's live document, so the page marks it active.
POLICY_REVISIONS: list[tuple[list[str], list[str], str]] = [
    (["https://api.anthropic.com"], [], "initial allowlist"),
    (["https://api.anthropic.com", "https://tickets.acme.io"], [], "allow the helpdesk API"),
    (
        ["https://api.anthropic.com", "https://tickets.acme.io"],
        ["https://paste.example.net"],
        "block paste sites after egress_deny",
    ),
    (
        ["https://api.anthropic.com", "https://tickets.acme.io", "https://docs.acme.io"],
        ["https://paste.example.net"],
        "allow the docs crawler",
    ),
]


async def _seed_policy_history(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    workspace = await db.get(Workspace, ctx.workspace_id)
    live_limits = {
        "llm_rate_limit_per_minute": getattr(workspace, "llm_rate_limit_per_minute", None),
        "tool_rate_limit_per_minute": getattr(workspace, "tool_rate_limit_per_minute", None),
        "llm_daily_quota": getattr(workspace, "llm_daily_quota", None),
        "tool_daily_quota": getattr(workspace, "tool_daily_quota", None),
    }
    total = len(POLICY_REVISIONS)
    for number, (allow, block, note) in enumerate(POLICY_REVISIONS, start=1):
        # Normalised the way the service reads a live policy, so the newest
        # revision's bundle id matches the workspace's and shows as active.
        document = PolicyDocument(
            egress_allowlist=allow, egress_blocklist=block, **live_limits
        ).model_dump()
        created = now - timedelta(days=(total - number) * 6 + 1)
        await _upsert(
            db,
            PolicyRevision,
            _sid("prev", ctx, f"workspace:{number}"),
            {
                "tenant_id": ctx.tenant_id,
                "scope": "workspace",
                "scope_id": ctx.workspace_id,
                "workspace_id": ctx.workspace_id,
                "revision": number,
                "bundle_id": policy_bundle_id(document),
                "document_json": document,
                "note": note,
                "created_by": ctx.user_id,
                "created_at": created,
            },
        )
        await _upsert(
            db,
            AuditEvent,
            _sid("aud", ctx, f"egress-policy:{number}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "event_type": "security.egress_policy.updated",
                "resource_type": "egress_policy",
                "resource_id": ctx.workspace_id,
                "trace_id": f"{TRACE_PREFIX}egress-policy:{number}",
                "outcome": "succeeded",
                "operation": "update",
                "actor_user_id": ctx.user_id,
                "scope": "workspace",
                "payload_json": {"allowlist": allow, "blocklist": block, "revision": number},
                "created_at": created,
            },
        )
    await db.commit()


# --------------------------------------------------------------------------- #
# knowledge ingest queue and chunks -- knowledge.html, knowledge detail
# --------------------------------------------------------------------------- #

#: Ingest tasks per knowledge index status, newest first. No `queued` row: the
#: API's in-process ingest worker claims one within a second and fails it,
#: because seeded documents carry no stored file. The running row holds a
#: long lease for the same reason.
INGEST_BY_STATUS: dict[str, list[str]] = {
    "ready": ["succeeded", "succeeded"],
    "building": ["running", "canceled", "succeeded"],
    "failed": ["failed", "succeeded"],
}


async def _seed_knowledge_activity(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    for spec in KNOWLEDGE:
        key = spec["key"]
        knowledge_id = _sid("knw", ctx, key)
        doc_id = _sid("doc", ctx, f"{key}:doc")
        document = await db.get(KnowledgeDocument, doc_id)
        failed_doc = spec["index_status"] == "failed"
        for order, status in enumerate(INGEST_BY_STATUS.get(spec["index_status"], [])):
            created = now - timedelta(hours=order * 8 + 1)
            finished = status in {"succeeded", "failed", "canceled"}
            await _upsert(
                db,
                KnowledgeIngestTask,
                _sid("ing", ctx, f"{key}:{order}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "knowledge_id": knowledge_id,
                    "document_id": doc_id,
                    "status": status,
                    "attempt_count": 3 if status == "failed" else 1,
                    "lease_owner": "seed:console_prototype" if status == "running" else None,
                    "lease_expires_at": now + timedelta(days=30) if status == "running" else None,
                    "payload_json": _meta(source_kind=spec["source_kind"]),
                    "error_code": "ocr_required" if status == "failed" else None,
                    "error_message": (
                        "3 scanned PDFs produced no extractable text."
                        if status == "failed"
                        else None
                    ),
                    "retry_count": 2 if status == "failed" else 0,
                    "max_retries": 2,
                    "started_at": None if status == "queued" else created,
                    "finished_at": created + timedelta(minutes=4) if finished else None,
                    "created_by": ctx.user_id,
                    "updated_by": ctx.user_id,
                    "created_at": created,
                },
            )
        if document is None:
            continue
        text = f"{spec['name']}: {spec['description']}"
        for chunk_no in range(4):
            preview = f"{text} -- section {chunk_no + 1}"
            await _upsert(
                db,
                KnowledgeChunk,
                _sid("chk", ctx, f"{key}:{chunk_no}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "knowledge_id": knowledge_id,
                    "document_id": doc_id,
                    "document_version": document.version,
                    "chunk_no": chunk_no,
                    "chunk_key": f"{key}#{chunk_no}",
                    "content_hash": hashlib.sha256(preview.encode()).hexdigest(),
                    "text_preview": preview,
                    "start_offset": chunk_no * 600,
                    "end_offset": chunk_no * 600 + 600,
                    "page_no": chunk_no + 1,
                    "section_path": [spec["name"], f"section {chunk_no + 1}"],
                    "source_meta_json": _meta(),
                    "char_count": 600,
                    "token_count": 140 + chunk_no * 11,
                    "embedding_model_ref": "model:vllm:bge-m3",
                    "indexed_at": None if failed_doc else now - timedelta(hours=8),
                    "index_status": "failed" if failed_doc else "indexed",
                    "index_error": "ocr_required" if failed_doc else None,
                },
            )
    await db.commit()


# --------------------------------------------------------------------------- #
# agent reviews and releases -- agents.html, agent detail
# --------------------------------------------------------------------------- #

#: Drafts waiting on review: (agent key, review status, note)
DRAFT_REVIEWS: list[tuple[str, str, str]] = [
    ("support-triage", "in_review", "adds the refund macro to the prompt"),
    ("billing-audit", "changes_requested", "tighten the journal.post scope first"),
]


async def _seed_agent_releases(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    for spec in AGENTS:
        key = spec["key"]
        agent_id = _sid("agt", ctx, key)
        current_id = _sid("agtv", ctx, key)
        current = await db.get(AgentVersion, current_id)
        if current is None or spec["status"] != "active":
            continue
        # Two earlier versions, so the release history shows a rollback and a
        # re-publish rather than a single row.
        history: list[tuple[str, int]] = []
        for back in (2, 1):
            number = max(1, int(spec["version"]) - back)
            version_id = _sid("agtv", ctx, f"{key}:v{number}")
            await _upsert(
                db,
                AgentVersion,
                version_id,
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "agent_id": agent_id,
                    "version": number,
                    "status": "archived",
                    "spec_schema": current.spec_schema,
                    "spec_json": dict(current.spec_json or {}),
                    "changelog": f"v{number}",
                    "created_by": ctx.user_id,
                    "created_at": now - timedelta(days=back * 9),
                },
            )
            history.append((version_id, back))
        # A rollback is its own release: it re-publishes an earlier version and
        # points at the release it restored.
        first_release = _sid("apub", ctx, f"{key}:1")
        releases = [
            (history[0][0], "published", 18, None, "first release in this workspace"),
            (history[1][0], "published", 12, None, "prompt tuning"),
            (history[0][0], "rolled_back", 9, first_release, "latency regression on long tickets"),
            (current_id, "published", 2, None, "current release"),
        ]
        for sequence, (version_id, status, days_ago, rollback_of, notes) in enumerate(
            releases, start=1
        ):
            await _upsert(
                db,
                AgentPublish,
                _sid("apub", ctx, f"{key}:{sequence}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "agent_id": agent_id,
                    "agent_version_id": version_id,
                    "sequence": sequence,
                    "scope": "workspace",
                    "status": status,
                    "notes": notes,
                    "rollback_of_publish_id": rollback_of,
                    "created_by": ctx.user_id,
                    "created_at": now - timedelta(days=days_ago),
                    "updated_at": now - timedelta(days=days_ago),
                },
            )
    reviewers = [email for email, _name, role in TEAMMATES if role in {"Admin", "Dev"}]
    for index, (key, review_status, note) in enumerate(DRAFT_REVIEWS):
        current = await db.get(AgentVersion, _sid("agtv", ctx, key))
        spec = next(item for item in AGENTS if item["key"] == key)
        if current is None:
            continue
        requested = now - timedelta(hours=3 + index * 20)
        await _upsert(
            db,
            AgentVersion,
            _sid("agtv", ctx, f"{key}:draft"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": _sid("agt", ctx, key),
                "version": int(spec["version"]) + 1,
                "status": "draft",
                "spec_schema": current.spec_schema,
                "spec_json": dict(current.spec_json or {}),
                "created_from_version_id": current.id,
                "changelog": note,
                "review_status": review_status,
                "review_requested_at": requested,
                "review_requested_by": ctx.user_id,
                "review_note": note if review_status == "changes_requested" else None,
                "reviewed_by": reviewers[index % len(reviewers)]
                if review_status == "changes_requested"
                else None,
                "reviewed_at": requested + timedelta(hours=2)
                if review_status == "changes_requested"
                else None,
                "created_by": ctx.user_id,
                "created_at": requested,
            },
        )
    await db.commit()


# --------------------------------------------------------------------------- #
# dead letters -- events.html
# --------------------------------------------------------------------------- #

#: (event type, consumer, error, hours ago). Failed ingest tasks, workflow runs
#: and tasks already land in the dead-letter view from the sections above.
FAILED_EVENTS: list[tuple[str, str, str, int]] = [
    ("run.completed", "webhook.delivery", "POST https://hooks.acme.io/soit returned 502", 2),
    ("approval.requested", "notification.fanout", "Slack API rate limited (429) after 5 attempts", 9),
    ("knowledge.document.indexed", "search.projection", "projection lag exceeded 15m", 30),
]


async def _seed_dead_letters(db: AsyncSession, ctx: RequestContext, run_ids: list[str]) -> None:
    now = utc_now()
    for index, (event_type, consumer, error, hours_ago) in enumerate(FAILED_EVENTS):
        event_row_id = _sid("evt", ctx, f"dead:{index}")
        occurred = now - timedelta(hours=hours_ago)
        await _upsert(
            db,
            EventOutbox,
            event_row_id,
            {
                "event_id": event_row_id,
                "event_type": event_type,
                "event_version": "v1",
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "idempotency_key": f"{SEED_SOURCE}:dead:{index}",
                "subject_type": "run",
                "subject_id": run_ids[index] if run_ids else None,
                "run_id": run_ids[index] if run_ids else None,
                "producer": "soit.runtime",
                "payload_json": _meta(),
                "headers_json": {},
                "status": "failed",
                "failed_consumer_name": consumer,
                "available_at": occurred,
                "attempt_count": 5,
                "last_error": error,
                "occurred_at": occurred,
                "created_at": occurred,
                "processed_at": occurred + timedelta(minutes=10),
            },
        )
    await db.commit()


# --------------------------------------------------------------------------- #
# knowledge queries -- knowledge.html tiles and per-library columns
# --------------------------------------------------------------------------- #

#: (knowledge key, queries today, failed). The index-failed library answers
#: nothing, which is what its hit rate should show. Healthy libraries fail
#: none: the workbench marks a library as errored on any failed run.
KNOWLEDGE_QUERIES: list[tuple[str, int, int]] = [
    ("product-docs", 42, 0),
    ("support-macros", 18, 0),
    ("runbooks", 9, 0),
    ("billing-policies", 4, 4),
]


async def _seed_knowledge_queries(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    # "Today" on the knowledge workbench is the UTC calendar day, so every
    # query run starts after midnight UTC.
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    span = max(60, int((now - midnight).total_seconds()) - 60)
    for key, count, failures in KNOWLEDGE_QUERIES:
        knowledge_id = _sid("knw", ctx, key)
        for index in range(count):
            suffix = f"kq:{key}:{index}"
            started = midnight + timedelta(seconds=span * (index + 1) // (count + 1))
            failed = index < failures
            duration_ms = 180 + (index % 9) * 45
            await _upsert(
                db,
                Run,
                _sid("run", ctx, suffix),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "user_id": ctx.user_id,
                    "trace_id": f"{TRACE_PREFIX}{suffix}",
                    "mode": "knowledge_query",
                    "kind": "api",
                    "subject_kind": "knowledge",
                    "subject_id": knowledge_id,
                    "status": "failed" if failed else "succeeded",
                    "input_summary": f"{key} query {index + 1}",
                    "output_summary": "" if failed else "3 chunks retrieved",
                    "started_at": started,
                    "ended_at": started + timedelta(milliseconds=duration_ms),
                    "duration_ms": duration_ms,
                    "created_at": started,
                    "error_code": "index_unavailable" if failed else None,
                    "error_message": "Knowledge index is not ready." if failed else None,
                },
            )
    await db.commit()


# --------------------------------------------------------------------------- #
# governance signals -- policies.html blocks, secrets.html resolutions
# --------------------------------------------------------------------------- #

#: (blocked domain, subject agent key, minutes ago)
EGRESS_BLOCKS: list[tuple[str, str, int]] = [
    ("paste.example.net", "billing-audit", 14),
    ("paste.example.net", "billing-audit", 75),
    ("files.unknown-cdn.io", "kb-refresher", 210),
    ("api.openai.com", "support-triage", 600),
]

#: (secret key, resolutions in the last 24h)
SECRET_RESOLUTIONS: list[tuple[str, int]] = [
    ("anthropic-prod", 9),
    ("SLACK_BOT_TOKEN", 4),
    ("helpdesk-api", 3),
]


async def _seed_governance_signals(
    db: AsyncSession, ctx: RequestContext, run_ids: list[str]
) -> None:
    now = utc_now()
    agent_ids = _ids(ctx, "agt", AGENTS)
    for index, (domain, agent_key, minutes_ago) in enumerate(EGRESS_BLOCKS):
        await _upsert(
            db,
            AuditEvent,
            _sid("aud", ctx, f"egress-block:{index}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "event_type": "security.egress.blocked",
                "resource_type": "egress",
                "resource_id": domain,
                "run_id": run_ids[index + 2] if len(run_ids) > index + 2 else None,
                "trace_id": f"{TRACE_PREFIX}egress-block:{index}",
                "outcome": "deny",
                "operation": "egress.block",
                "actor_user_id": ctx.user_id,
                "scope": "workspace",
                "payload_json": _meta(
                    resource_ref=f"agent:{agent_ids.get(agent_key, agent_key)}",
                    url=f"https://{domain}/",
                ),
                "created_at": now - timedelta(minutes=minutes_ago),
            },
        )
    for key, count in SECRET_RESOLUTIONS:
        secret_id = _sid("sec", ctx, key)
        for index in range(count):
            await _upsert(
                db,
                AuditEvent,
                _sid("aud", ctx, f"secret-resolved:{key}:{index}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "event_type": "security.secret.resolved",
                    "resource_type": "secret",
                    "resource_id": secret_id,
                    "trace_id": f"{TRACE_PREFIX}secret-resolved:{key}:{index}",
                    "outcome": "allow",
                    "operation": "secret.resolve",
                    "actor_user_id": ctx.user_id,
                    "scope": "workspace",
                    "payload_json": _meta(secret_ref=f"vault:{key}"),
                    "created_at": now - timedelta(minutes=20 + index * 97),
                },
            )
    # A secret that was never rotated, so "needs attention" has a subject.
    await _upsert(
        db,
        Secret,
        _sid("sec", ctx, "erp-service-account"),
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "name": "erp-service-account",
            "description": "service account for the ERP connector (never rotated)",
            "secret_ref": "vault:erp-service-account",
            "last_rotated_at": None,
            "created_by": ctx.user_id,
            "updated_by": ctx.user_id,
            "created_at": now - timedelta(days=120),
        },
    )
    await db.commit()


# --------------------------------------------------------------------------- #
# evaluations and evidence -- agent publish tab, run detail
# --------------------------------------------------------------------------- #

#: (cases, passed, avg latency ms) per report, oldest first.
REGRESSION_SERIES: list[tuple[int, int, int]] = [
    (40, 35, 4200),
    (40, 37, 3900),
    (42, 38, 4100),
    (42, 41, 3600),
    (44, 43, 3400),
]


async def _seed_regressions(db: AsyncSession, ctx: RequestContext) -> None:
    now = utc_now()
    for spec in AGENTS:
        if spec["status"] != "active":
            continue
        key = spec["key"]
        previous: str | None = None
        for index, (total, passed, latency) in enumerate(REGRESSION_SERIES):
            report_id = _sid("rgr", ctx, f"{key}:{index}")
            await _upsert(
                db,
                RegressionReport,
                report_id,
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "subject_kind": "agent",
                    "subject_id": _sid("agt", ctx, key),
                    "subject_version_id": _sid("agtv", ctx, key),
                    "passed": passed == total,
                    "dataset": f"{key}-golden",
                    "dataset_revision": index + 1,
                    "baseline_report_id": previous,
                    "regressed_case_ids_json": [],
                    "fixed_case_ids_json": [],
                    "summary_json": {"total": total, "passed": passed, "failed": total - passed},
                    "metrics_json": {"avg_latency_ms": latency},
                    "case_results_json": [],
                    "created_by": ctx.user_id,
                    "created_at": now - timedelta(days=(len(REGRESSION_SERIES) - index) * 4),
                },
            )
            previous = report_id
    await db.commit()


async def _seed_run_artifacts(db: AsyncSession, ctx: RequestContext) -> None:
    """A JSON evidence artifact per named run, stored where the runtime puts them.

    The bytes go to object storage when it is reachable, so downloading an
    artifact from the run page returns the file rather than a missing key.
    """
    import json

    try:
        from app.wiring.container import get_container

        storage = get_container().get("storage_port")
    except Exception:  # noqa: BLE001 -- storage is optional for the seed
        storage = None
    for suffix, agent_key, kind, status, _duration, error in RUNS:
        run_id = _sid("run", ctx, suffix)
        body = json.dumps(
            {
                "run_id": run_id,
                "agent": agent_key,
                "trigger": kind,
                "status": status,
                "error": error,
            },
            indent=2,
        ).encode()
        key = (
            f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/runs/{run_id}/"
            "evidence/summary.json"
        )
        if storage is not None:
            try:
                await storage.put(key, body, content_type="application/json")
            except Exception:  # noqa: BLE001 -- metadata still renders
                pass
        await _upsert(
            db,
            RunArtifact,
            _sid("art", ctx, f"{suffix}:summary"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "run_id": run_id,
                "step_id": _sid("step", ctx, f"{suffix}:tool"),
                "type": "json",
                "mime": "application/json",
                "size_bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "storage_key": key,
                "meta_json": _meta(kind="evidence.summary"),
            },
        )
    await db.commit()

# --------------------------------------------------------------------------- #
# entrypoints
# --------------------------------------------------------------------------- #


async def reset_operations(db: AsyncSession, ctx: RequestContext) -> None:
    """Delete this module's rows. The prototype reset covers shared tables."""
    from sqlalchemy import and_, select

    suffix = "_proto_"
    for model in RESET_MODELS:
        clauses = [model.tenant_id == ctx.tenant_id]
        if hasattr(model, "workspace_id"):
            clauses.append(model.workspace_id == ctx.workspace_id)
        rows = (await db.exec(select(model).where(and_(*clauses)))).scalars().all()
        for row in rows:
            if suffix in str(row.id):
                await db.delete(row)
    for model in (EventOutbox,):
        rows = (
            await db.exec(
                select(model).where(
                    and_(model.tenant_id == ctx.tenant_id, model.workspace_id == ctx.workspace_id)
                )
            )
        ).scalars().all()
        for row in rows:
            if suffix in str(row.id):
                await db.delete(row)
    await db.commit()


async def seed_operations(
    db: AsyncSession, ctx: RequestContext, run_ids: list[str]
) -> dict[str, int]:
    """Seed the operational history; returns a count per surface."""
    workflow_runs = await _seed_workflow_runs(db, ctx)
    schedules = await _seed_schedules(db, ctx, workflow_runs)
    await _seed_task_history(db, ctx, run_ids)
    await _seed_approval_history(db, ctx, run_ids)
    await _seed_notifications(db, ctx)
    await _seed_shortcuts(db, ctx)
    await _seed_grants(db, ctx)
    await _seed_feedback(db, ctx)
    await _seed_policy_history(db, ctx)
    await _seed_knowledge_activity(db, ctx)
    await _seed_agent_releases(db, ctx)
    await _seed_dead_letters(db, ctx, run_ids)
    await _seed_knowledge_queries(db, ctx)
    await _seed_governance_signals(db, ctx, run_ids)
    await _seed_regressions(db, ctx)
    await _seed_run_artifacts(db, ctx)
    return {
        "workflow_runs": sum(len(ids) for ids in workflow_runs.values()),
        "schedules": len(schedules),
        "approvals_decided": len(DECIDED_APPROVALS),
        "notifications": len(NOTIFICATIONS),
        "notification_endpoints": len(NOTIFICATION_ENDPOINTS),
        "pins": len(PINS),
        "saved_views": len(SAVED_VIEWS),
        "grants": len(GRANTS),
        "feedback": len(FEEDBACK),
        "policy_revisions": len(POLICY_REVISIONS),
        "draft_reviews": len(DRAFT_REVIEWS),
        "dead_letter_events": len(FAILED_EVENTS),
        "knowledge_queries": sum(count for _key, count, _failed in KNOWLEDGE_QUERIES),
        "egress_blocks": len(EGRESS_BLOCKS),
        "secret_resolutions": sum(count for _key, count in SECRET_RESOLUTIONS),
        "regression_reports": len(REGRESSION_SERIES)
        * sum(1 for spec in AGENTS if spec["status"] == "active"),
        "run_artifacts": len(RUNS),
    }
