"""Seed the console with the objects the v13 prototype shows.

A fresh install answers every console list with an empty page, so the screens
cannot be reviewed against the prototype without hand-building a workspace
first. This seeds exactly the objects the prototype draws -- the same agents,
workflows, knowledge bases, plugins, models, secrets, threads, runs, tasks and
approvals, under their prototype names -- so the console fills out the way the
design says it should.

It is deliberately separate from ``seed_enterprise_mvp_scenarios``: that script
backs integration tests and the release verification scripts, and its rows carry
a different scenario. The two use different id prefixes and different seed
markers, so ``--reset`` on either one leaves the other alone.

Usage::

    python -m scripts.seed_console_prototype --reset
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets as pysecrets
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import and_, select

from app.infra.db.session import get_db_sync
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.modules.agent.domain.models import Agent, AgentBinding, AgentVersion
from app.modules.billing.domain.models import CreditLedgerEntry
from app.modules.identity.domain.models import (
    ApiKey,
    TenantMembership,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeDocument,
    KnowledgeIndex,
)
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginVersion,
)
from app.modules.secrets.domain.models import Secret
from app.modules.workflow.domain.models import Workflow, WorkflowVersion

# Only the identity half of the MVP bootstrap: it creates the tenant, workspace
# and owner this seed needs. The full bootstrap would also plant its own demo
# agent, workflow, knowledge base and secret, which would show up in the console
# alongside the prototype's objects and put every list one row over.
from scripts.bootstrap_enterprise_mvp import _ensure_context

SEED_SOURCE = "console_prototype"
#: Distinct from the MVP seed's ``_seed_`` infix so neither reset touches the
#: other's rows.
ID_INFIX = "proto"
TRACE_PREFIX = f"trace:{SEED_SOURCE}:"


class PrototypeSeedSummary(BaseModel):
    """Stable output index for the seeded prototype workspace."""

    tenant_id: str
    workspace_id: str
    user_id: str
    agent_ids: list[str] = Field(default_factory=list)
    workflow_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    plugin_ids: list[str] = Field(default_factory=list)
    model_refs: list[str] = Field(default_factory=list)
    secret_ids: list[str] = Field(default_factory=list)
    thread_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    approval_ids: list[str] = Field(default_factory=list)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="12345678")
    parser.add_argument("--name", default="Jude")
    parser.add_argument("--tenant-name", default="default")
    parser.add_argument("--workspace-name", default="default")
    parser.add_argument(
        "--reset", action="store_true", help="delete this seed's rows first"
    )
    # The prototype's side panel reports 1,284 runs and 14 tasks in the window
    # its tables sample. Seeding only the named rows would leave the panel
    # claiming a volume the pages visibly do not have.
    parser.add_argument("--runs", type=int, default=1284, help="total runs to seed")
    parser.add_argument("--tasks", type=int, default=14, help="total tasks to seed")
    parser.add_argument("--json-output", default=None)
    return parser.parse_args()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _unwrap(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, tuple):
        return row[0]
    try:
        return row[0]
    except Exception:
        return row


def _sid(prefix: str, ctx: RequestContext, key: str) -> str:
    digest = hashlib.sha1(
        f"{ctx.tenant_id}:{ctx.workspace_id}:{key}".encode()
    ).hexdigest()[:16]
    return f"{prefix}_{ID_INFIX}_{digest}"


def _meta(**extra: Any) -> dict[str, Any]:
    return {"seed_source": SEED_SOURCE, **extra}


def _upsert(db, model: type[Any], item_id: str, values: dict[str, Any]):
    item = db.get(model, item_id)
    if item is None:
        item = model(id=item_id, **values)
    else:
        for key, value in values.items():
            setattr(item, key, value)
        if hasattr(item, "updated_at"):
            item.updated_at = utc_now()
    db.add(item)
    return item


def _scoped(model: type[Any], ctx: RequestContext):
    return select(model).where(
        and_(model.tenant_id == ctx.tenant_id, model.workspace_id == ctx.workspace_id)
    )


def _delete(db, items: Iterable[Any]) -> None:
    for item in items:
        db.delete(item)


def _reset(db, ctx: RequestContext) -> None:
    """Delete only this seed's rows, identified by the id infix.

    Children go before parents so a foreign key never blocks the delete, and
    every model is filtered on the workspace as well as the infix -- a stray id
    collision must not reach another tenant's data.
    """
    suffix = f"_{ID_INFIX}_"
    ordered = (
        ThreadMessage,
        CreditLedgerEntry,
        RunCostEntry,
        RunStep,
        ApprovalRequest,
        Task,
        Run,
        Thread,
        AuditEvent,
        AgentBinding,
        AgentVersion,
        Agent,
        WorkflowVersion,
        Workflow,
        KnowledgeDocument,
        KnowledgeIndex,
        Knowledge,
        PluginInstallation,
        PluginVersion,
        Plugin,
        ProviderModel,
        Provider,
        Secret,
    )
    for model in ordered:
        rows = [_unwrap(row) for row in db.exec(_scoped(model, ctx)).all()]
        _delete(db, [row for row in rows if suffix in str(row.id)])
    db.commit()


# --------------------------------------------------------------------------- #
# model hub -- models.html
# --------------------------------------------------------------------------- #

PROVIDERS: list[dict[str, Any]] = [
    {
        "key": "anthropic",
        "name": "Anthropic",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com",
        "models": [
            {
                "key": "claude-sonnet-5",
                "model_id": "claude-sonnet-5",
                "display": "claude-sonnet-5",
                "context": 200_000,
                "caps": {"chat": True, "tool_calls": True, "vision": True},
                "status": "active",
            },
            {
                "key": "claude-haiku-45",
                "model_id": "claude-haiku-4.5",
                "display": "claude-haiku-4.5",
                "context": 200_000,
                "caps": {"chat": True, "tool_calls": True},
                "status": "active",
            },
        ],
    },
    {
        "key": "dashscope",
        "name": "DashScope",
        "kind": "dashscope",
        "base_url": "https://dashscope.aliyuncs.com",
        "models": [
            {
                "key": "qwen3-235b",
                "model_id": "qwen3-235b",
                "display": "qwen3-235b",
                "context": 128_000,
                "caps": {"chat": True, "tool_calls": True},
                "status": "active",
            },
        ],
    },
    {
        "key": "vllm",
        "name": "vLLM",
        "kind": "vllm",
        "base_url": "http://vllm.internal:8000",
        "models": [
            {
                "key": "qwen3-30b-local",
                "model_id": "qwen3-30b-local",
                "display": "qwen3-30b-local",
                "context": 32_000,
                "caps": {"chat": True},
                "status": "active",
            },
            {
                "key": "bge-m3",
                "model_id": "bge-m3",
                "display": "bge-m3",
                "context": 8_000,
                "caps": {"embeddings": True},
                "status": "active",
            },
            {
                "key": "bge-reranker",
                "model_id": "bge-reranker",
                "display": "bge-reranker",
                "context": 8_000,
                "caps": {"rerank": True},
                "status": "active",
            },
        ],
    },
]


def _seed_modelhub(db, ctx: RequestContext) -> list[str]:
    refs: list[str] = []
    for spec in PROVIDERS:
        provider = _upsert(
            db,
            Provider,
            _sid("prov", ctx, spec["key"]),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "kind": spec["kind"],
                "name": spec["name"],
                "base_url": spec["base_url"],
                "credential_secret_id": _sid("sec", ctx, "anthropic-prod"),
                "status": "active",
                "sync_policy_json": _meta(auto_sync=False),
                "last_healthcheck_at": utc_now(),
                "last_healthcheck_error": None,
            },
        )
        for model in spec["models"]:
            _upsert(
                db,
                ProviderModel,
                _sid("pmdl", ctx, model["key"]),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "provider_id": provider.id,
                    "provider_kind": spec["kind"],
                    "model_id": model["model_id"],
                    "display_name": model["display"],
                    "description": f"{spec['name']} {model['display']}.",
                    "capabilities_json": model["caps"],
                    "config_json": _meta(),
                    "context_window": model["context"],
                    "max_output_tokens": 8192,
                    "lifecycle_status": "generally_available",
                    "raw_meta": _meta(),
                    "status": model["status"],
                    "source": "local",
                    "sync_status": "in_sync",
                },
            )
            refs.append(f"model:{spec['kind']}:{model['model_id']}")
    db.commit()
    return refs


# --------------------------------------------------------------------------- #
# knowledge -- knowledge.html
# --------------------------------------------------------------------------- #

KNOWLEDGE: list[dict[str, Any]] = [
    {
        "key": "product-docs",
        "name": "product-docs",
        "description": "public docs site + changelog",
        "source_kind": "crawler",
        "status": "active",
        "index_status": "ready",
        "docs": 1204,
        "chunks": 18392,
    },
    {
        "key": "support-macros",
        "name": "support-macros",
        "description": "canned replies and escalation macros",
        "source_kind": "manual",
        "status": "active",
        "index_status": "ready",
        "docs": 86,
        "chunks": 1022,
    },
    {
        "key": "runbooks",
        "name": "runbooks",
        "description": "on-call runbooks from the ops repo",
        "source_kind": "git",
        "status": "active",
        "index_status": "building",
        "docs": 312,
        "chunks": 4410,
    },
    {
        "key": "billing-policies",
        "name": "billing-policies",
        "description": "scanned PDFs",
        "source_kind": "manual",
        "status": "active",
        "index_status": "failed",
        "docs": 24,
        "chunks": 388,
    },
]


def _seed_knowledge(db, ctx: RequestContext) -> list[Knowledge]:
    now = utc_now()
    items: list[Knowledge] = []
    for spec in KNOWLEDGE:
        knowledge_id = _sid("knw", ctx, spec["key"])
        index_id = _sid("idx", ctx, spec["key"])
        degraded = spec["index_status"] == "failed"
        knowledge = _upsert(
            db,
            Knowledge,
            knowledge_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": spec["name"],
                "type": "document",
                "description": spec["description"],
                "status": spec["status"],
                "visibility": "workspace",
                "settings_json": _meta(source_kind=spec["source_kind"]),
                "chunking_json": {"chunk_size": 600, "overlap": 80},
                "retrieval_json": {"top_k": 3, "rerank": False},
                "default_embedding_model_ref": "model:vllm:bge-m3",
                "default_index_id": index_id,
                "doc_count": spec["docs"],
                "chunk_count": spec["chunks"],
                "last_ingested_at": now - timedelta(hours=8),
                "last_indexed_at": None if degraded else now - timedelta(hours=8),
                "tags": ["prototype", spec["key"]],
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        _upsert(
            db,
            KnowledgeIndex,
            index_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "knowledge_id": knowledge_id,
                "name": f"{spec['key']}-primary",
                "is_primary": True,
                "provider": "file-backed",
                "collection_name": f"proto_{knowledge_id}",
                "embedding_model_ref": "model:vllm:bge-m3",
                "dimension": 1024,
                "metric_type": "cosine",
                "index_params_json": _meta(profile="local"),
                "search_params_json": {"top_k": 3},
                "filters_json": {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                },
                "status": spec["index_status"],
                "doc_count": spec["docs"],
                "chunk_count": spec["chunks"],
                "vector_count": spec["chunks"],
                "last_build_at": now - timedelta(hours=8),
                "last_error_code": "ocr_required" if degraded else None,
                "last_error_message": (
                    "3 scanned PDFs produced no extractable text." if degraded else None
                ),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        # One representative document per base: the console lists documents, and
        # an empty document tab on a base reporting 1,204 docs reads as a bug.
        doc_id = _sid("doc", ctx, f"{spec['key']}:doc")
        text = f"{spec['name']}: {spec['description']}"
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        _upsert(
            db,
            KnowledgeDocument,
            doc_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "knowledge_id": knowledge_id,
                "doc_key": f"{spec['key']}.md",
                "version": 1,
                "is_latest": True,
                "source_kind": spec["source_kind"],
                "source_uri": f"kb://prototype/{spec['key']}.md",
                "title": spec["name"],
                "language": "en",
                "mime_type": "text/markdown",
                "filename": f"{spec['key']}.md",
                "size_bytes": len(text.encode("utf-8")),
                "checksum": checksum,
                "content_hash": checksum,
                "status": "failed" if degraded else "indexed",
                "error_code": "ocr_required" if degraded else None,
                "error_message": (
                    "Scanned PDF produced no extractable text." if degraded else None
                ),
                "retry_count": 1 if degraded else 0,
                "parse_meta_json": _meta(pages=1),
                "index_meta_json": {"index_id": index_id, "chunk_count": 1},
                "access_policy_json": {"visibility": "workspace"},
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        items.append(knowledge)
    db.commit()
    return items


# --------------------------------------------------------------------------- #
# workflows -- workflows.html
# --------------------------------------------------------------------------- #

WORKFLOWS: list[dict[str, Any]] = [
    {
        "key": "ticket-escalation",
        "name": "ticket-escalation",
        "summary": "triage → enrich → route",
        "version": 14,
        "status": "active",
        "published": True,
        "nodes": 9,
    },
    {
        "key": "invoice-reconcile",
        "name": "invoice-reconcile",
        "summary": "fetch → diff → post",
        "version": 8,
        "status": "active",
        "published": True,
        "nodes": 7,
    },
    {
        "key": "docs-nightly-sync",
        "name": "docs-nightly-sync",
        "summary": "crawl → chunk → embed → verify",
        "version": 22,
        "status": "active",
        "published": True,
        "nodes": 12,
    },
    {
        "key": "release-digest",
        "name": "release-digest",
        "summary": "collect PRs → summarise → publish",
        "version": 5,
        "status": "active",
        "published": True,
        "nodes": 5,
    },
    {
        "key": "churn-signal-scan",
        "name": "churn-signal-scan",
        "summary": "query → score → draft",
        "version": 2,
        "status": "draft",
        "published": False,
        "nodes": 6,
    },
]


def _graph(spec: dict[str, Any]) -> dict[str, Any]:
    """A linear graph of the node count the workflow list reports.

    The builder reads this, so the shape has to be valid rather than decorative:
    a start, N-2 tool steps, an output, wired in order.
    """
    count = max(3, int(spec["nodes"]))
    nodes = [{"id": "start", "type": "set_var", "params": {"workflow": spec["key"]}}]
    for index in range(1, count - 1):
        nodes.append(
            {
                "id": f"step_{index}",
                "type": "tool",
                "params": {"tool_ref": "builtin.ticket.create_review_ticket"},
            }
        )
    nodes.append({"id": "end", "type": "output", "params": {"status": "ok"}})
    edges = [
        {"id": f"e{index}", "from": nodes[index]["id"], "to": nodes[index + 1]["id"]}
        for index in range(len(nodes) - 1)
    ]
    return _meta(
        name=spec["name"],
        graph={"nodes": nodes, "edges": edges},
        inputs_schema={"type": "object"},
        outputs_schema={"type": "object"},
    )


def _seed_workflows(db, ctx: RequestContext) -> list[Workflow]:
    items: list[Workflow] = []
    for spec in WORKFLOWS:
        workflow_id = _sid("wf", ctx, spec["key"])
        version_id = _sid("wfv", ctx, spec["key"])
        workflow = _upsert(
            db,
            Workflow,
            workflow_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": spec["name"],
                "description": spec["summary"],
                "summary": spec["summary"],
                "status": spec["status"],
                "visibility": "workspace",
                "category": "prototype",
                "tags": ["prototype"],
                "owner_user_id": ctx.user_id,
                "metadata_json": _meta(node_count=spec["nodes"]),
                "current_version_id": version_id,
                "published_version_id": version_id if spec["published"] else None,
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        _upsert(
            db,
            WorkflowVersion,
            version_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "workflow_id": workflow_id,
                "version": spec["version"],
                "status": "published" if spec["published"] else "draft",
                "spec_schema": "workflow.v1",
                "spec_json": _graph(spec),
                "created_by": ctx.user_id,
            },
        )
        items.append(workflow)
    db.commit()
    return items


# --------------------------------------------------------------------------- #
# agents -- agents.html
# --------------------------------------------------------------------------- #

AGENTS: list[dict[str, Any]] = [
    {
        "key": "support-triage",
        "name": "support-triage",
        "description": "first-line ticket triage with citation-backed replies",
        "category": "support",
        "status": "active",
        "version": 12,
        "model": "model:anthropic:claude-sonnet-5",
        "knowledge": ["product-docs", "support-macros"],
        "workflows": ["ticket-escalation"],
    },
    {
        "key": "ops-copilot",
        "name": "ops-copilot",
        "description": "cluster operations copilot for the on-call rotation",
        "category": "operations",
        "status": "active",
        "version": 9,
        "model": "model:anthropic:claude-sonnet-5",
        "knowledge": ["runbooks"],
        "workflows": [],
    },
    {
        "key": "kb-refresher",
        "name": "kb-refresher",
        "description": "keeps the docs knowledge base current",
        "category": "knowledge",
        "status": "active",
        "version": 22,
        "model": "model:anthropic:claude-haiku-4.5",
        "knowledge": ["product-docs"],
        "workflows": ["docs-nightly-sync"],
    },
    {
        "key": "billing-audit",
        "name": "billing-audit",
        "description": "invoice checks against the billing policy base",
        "category": "finance",
        "status": "active",
        "version": 6,
        "model": "model:dashscope:qwen3-235b",
        "knowledge": ["billing-policies"],
        "workflows": ["invoice-reconcile"],
    },
    {
        "key": "release-notes",
        "name": "release-notes",
        "description": "drafts release notes from merged pull requests",
        "category": "engineering",
        "status": "active",
        "version": 5,
        "model": "model:anthropic:claude-haiku-4.5",
        "knowledge": [],
        "workflows": ["release-digest"],
    },
    {
        "key": "quota-sentinel",
        "name": "quota-sentinel",
        "description": "watches per-team model spend against budget",
        "category": "finance",
        "status": "paused",
        "version": 3,
        "model": "model:vllm:qwen3-30b-local",
        "knowledge": [],
        "workflows": [],
    },
]


def _seed_agents(
    db,
    ctx: RequestContext,
    knowledge: dict[str, str],
    workflows: dict[str, str],
) -> list[Agent]:
    now = utc_now()
    items: list[Agent] = []
    for spec in AGENTS:
        agent_id = _sid("agt", ctx, spec["key"])
        version_id = _sid("agtv", ctx, spec["key"])
        published = spec["status"] == "active"
        agent = _upsert(
            db,
            Agent,
            agent_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": spec["name"],
                "description": spec["description"],
                "status": spec["status"],
                "visibility": "workspace",
                "category": spec["category"],
                "featured": False,
                "tags": ["prototype", spec["category"]],
                "profile_json": _meta(persona=spec["category"]),
                "instructions_json": {"system_prompt": spec["description"]},
                "execution_policy_json": {
                    "max_iterations": 4,
                    "require_citations": True,
                },
                "runtime_config_json": {"rag_top_k": 3, "tool_timeout_ms": 5000},
                "default_model_ref": spec["model"],
                "current_version_id": version_id,
                "published_version_id": version_id if published else None,
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
                "published_at": now if published else None,
            },
        )
        _upsert(
            db,
            AgentVersion,
            version_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agent_id,
                "version": spec["version"],
                "status": "published" if published else "draft",
                "spec_schema": "agent.v1",
                "spec_json": _meta(
                    name=spec["name"],
                    model_ref=spec["model"],
                    system_prompt=spec["description"],
                ),
                "created_by": ctx.user_id,
            },
        )
        bindings: list[tuple[str, str]] = [("model", spec["model"])]
        bindings += [
            ("knowledge", knowledge[key])
            for key in spec["knowledge"]
            if key in knowledge
        ]
        bindings += [
            ("workflow", workflows[key])
            for key in spec["workflows"]
            if key in workflows
        ]
        for order, (kind, ref) in enumerate(bindings):
            _upsert(
                db,
                AgentBinding,
                _sid("agtb", ctx, f"{spec['key']}:{kind}:{ref}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "agent_id": agent_id,
                    "agent_version_id": version_id,
                    "binding_type": kind,
                    # A model binding points at a ref string, the others at a row
                    # id; the column pair is target_id / target_key, not one ref.
                    "target_id": None if kind == "model" else ref,
                    "target_key": ref if kind == "model" else None,
                    "config_json": _meta(),
                    "sort_order": order,
                },
            )
        items.append(agent)
    db.commit()
    return items


# --------------------------------------------------------------------------- #
# plugins -- plugins.html
# --------------------------------------------------------------------------- #

PLUGINS: list[dict[str, Any]] = [
    (
        "k8s-toolkit",
        "mcp_server",
        "1.4.2",
        "soit-labs",
        ["k8s.read", "k8s.rollout", "k8s.logs"],
        True,
    ),
    (
        "helpdesk-api",
        "tool",
        "2.0.1",
        "builtin",
        ["tickets.read", "tickets.write"],
        True,
    ),
    ("vault-secrets", "mcp_server", "0.9.8", "builtin", ["secrets.ref"], True),
    ("web-fetch", "tool", "1.1.0", "soit-labs", ["net.egress"], True),
    (
        "erp-connector",
        "mcp_server",
        "3.2.0",
        "finance-it",
        ["finance.journal.post"],
        True,
    ),
    ("cdn-tools", "tool", "0.3.1", "community", ["cdn.purge"], False),
    ("incident-writeup", "skill", "1.2.0", "soit-labs", [], True),
    ("runbook-triage", "skill", "0.4.1", "community", ["k8s.read"], True),
]


def _seed_plugins(db, ctx: RequestContext) -> list[str]:
    ids: list[str] = []
    for name, plugin_type, version, publisher, scopes, installed in PLUGINS:
        plugin_id = _sid("plg", ctx, name)
        version_id = _sid("plgv", ctx, name)
        spec_json = {"plugin_type": plugin_type, "exports": {"scopes": scopes}}
        manifest_json = {"name": name, "version": version, "enabled": installed}
        _upsert(
            db,
            Plugin,
            plugin_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": name,
                "version": version,
                "publisher": publisher,
                "plugin_type": plugin_type,
                "status": "active",
                "description": f"{name} ({plugin_type}) from {publisher}.",
                "spec_json": spec_json,
                "manifest_json": manifest_json,
                "metadata_json": _meta(scopes=scopes),
                "publish_status": "published",
                "installed_count": 1 if installed else 0,
                "current_version_id": version_id,
                "published_version_id": version_id,
                "created_by": ctx.user_id,
            },
        )
        _upsert(
            db,
            PluginVersion,
            version_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "plugin_id": plugin_id,
                "version": 1,
                "package_version": version,
                "status": "published",
                "spec_schema": "plugin.v1",
                "spec_json": spec_json,
                "manifest_json": manifest_json,
                "artifact_summary_json": spec_json["exports"],
                "metadata_json": _meta(),
                "created_by": ctx.user_id,
            },
        )
        if installed:
            _upsert(
                db,
                PluginInstallation,
                _sid("inst", ctx, name),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "plugin_id": plugin_id,
                    "plugin_version_id": version_id,
                    "enabled": True,
                    "state": "installed",
                    "installed_by": ctx.user_id,
                    "config_json": _meta(),
                },
            )
        ids.append(plugin_id)
    db.commit()
    return ids


# --------------------------------------------------------------------------- #
# secrets -- secrets.html
# --------------------------------------------------------------------------- #

SECRETS: list[tuple[str, str, int]] = [
    ("anthropic-prod", "API key for the Anthropic gateway", 14),
    ("k8s-staging", "kubeconfig for the staging cluster", 30),
    ("SLACK_BOT_TOKEN", "bot token for incident notifications", 0),
    ("helpdesk-api", "token for the helpdesk API", 81),
]


def _seed_secrets(db, ctx: RequestContext) -> list[str]:
    now = utc_now()
    ids: list[str] = []
    for name, description, rotated_days in SECRETS:
        secret_id = _sid("sec", ctx, name)
        _upsert(
            db,
            Secret,
            secret_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": name,
                # The value is never seeded: secrets are write-only, and a
                # placeholder here would be a real credential-shaped string in
                # a demo database.
                "description": description,
                "secret_ref": f"vault:{name}",
                "last_rotated_at": now - timedelta(days=rotated_days, hours=6),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        ids.append(secret_id)
    db.commit()
    return ids


# --------------------------------------------------------------------------- #
# runs -- runs.html
# --------------------------------------------------------------------------- #

#: Failed runs in the seeded window, matching the "Failed only" saved view.
FAILED_TARGET = 15

RUNS: list[dict[str, Any]] = [
    ("01J9KD84QF", "support-triage", "webhook", "running", 3100, None),
    ("01J9KD7Z2M", "ops-copilot", "chat", "succeeded", 8900, None),
    ("01J9KD6H0T", "billing-audit", "schedule", "failed", 1200, "egress_blocked"),
    ("01J9KD5PWB", "support-triage", "webhook", "succeeded", 4400, None),
    ("01J9KD4XN2", "kb-refresher", "schedule", "succeeded", 21700, None),
    ("01J9KD3F7Q", "ops-copilot", "chat", "succeeded", 6000, None),
    ("01J9KD2M9C", "release-notes", "api", "succeeded", 5500, None),
    ("01J9KD1T4H", "support-triage", "webhook", "succeeded", 3800, None),
    ("01J9KD0S8V", "quota-sentinel", "schedule", "succeeded", 900, None),
]


def _seed_runs(
    db, ctx: RequestContext, agents: dict[str, str], total: int
) -> list[str]:
    now = utc_now()
    ids: list[str] = []
    for offset, (suffix, agent_key, kind, status, duration_ms, error) in enumerate(
        RUNS
    ):
        run_id = _sid("run", ctx, suffix)
        started = now - timedelta(minutes=4 * (offset + 1))
        ended = (
            None
            if status == "running"
            else started + timedelta(milliseconds=duration_ms)
        )
        _upsert(
            db,
            Run,
            run_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "user_id": ctx.user_id,
                "trace_id": f"{TRACE_PREFIX}{suffix}",
                "mode": "agent",
                "kind": kind,
                "subject_kind": "agent",
                "subject_id": agents.get(agent_key, agent_key),
                "status": status,
                "input_summary": f"{agent_key} · {kind}",
                "output_summary": ""
                if status == "running"
                else f"{agent_key} completed",
                "started_at": started,
                "ended_at": ended,
                "duration_ms": None if ended is None else duration_ms,
                "error_code": error,
                "error_message": (
                    "Egress destination not in the workspace allowlist."
                    if error
                    else None
                ),
            },
        )
        for order, (step_key, step_type, step_status) in enumerate(
            (
                ("plan", "agent_plan", "succeeded"),
                ("retrieve", "retrieval", "succeeded"),
                ("tool", "tool", "failed" if error else "succeeded"),
            )
        ):
            _upsert(
                db,
                RunStep,
                _sid("step", ctx, f"{suffix}:{step_key}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "run_id": run_id,
                    "step_id": f"step-{order}",
                    "step_type": step_type,
                    "status": step_status,
                    "started_at": started,
                    "ended_at": ended,
                    "metrics_json": _meta(latency_ms=duration_ms // 3),
                },
            )
        ids.append(run_id)

    # Filler runs carrying the prototype's reported volume and failure mix:
    # 15 failed in the window, the rest succeeded. They are spread over 24h so
    # a windowed query sees the same shape the prototype describes.
    agent_keys = [spec["key"] for spec in AGENTS]
    kinds = ("webhook", "chat", "schedule", "api")
    bulk = max(0, total - len(RUNS))
    # FAILED_TARGET counts every failure in the window, and one of the named runs
    # is already failed, so the filler supplies the rest.
    named_failures = sum(1 for row in RUNS if row[5])
    filler_failures = max(0, FAILED_TARGET - named_failures)
    stride = max(1, bulk // filler_failures) if filler_failures else 0
    failures_placed = 0
    for index in range(len(RUNS), max(len(RUNS), total)):
        suffix = f"bulk{index:05d}"
        run_id = _sid("run", ctx, suffix)
        agent_key = agent_keys[index % len(agent_keys)]
        failed = (
            failures_placed < filler_failures
            and stride
            and (index - len(RUNS)) % stride == 0
        )
        if failed:
            failures_placed += 1
        started = now - timedelta(minutes=(index * 1080) // max(1, total) + 5)
        duration_ms = 900 + (index % 40) * 300
        _upsert(
            db,
            Run,
            run_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "user_id": ctx.user_id,
                "trace_id": f"{TRACE_PREFIX}{suffix}",
                "mode": "agent",
                "kind": kinds[index % len(kinds)],
                "subject_kind": "agent",
                "subject_id": agents.get(agent_key, agent_key),
                "status": "failed" if failed else "succeeded",
                "input_summary": f"{agent_key} · {kinds[index % len(kinds)]}",
                "output_summary": "" if failed else f"{agent_key} completed",
                "started_at": started,
                "ended_at": started + timedelta(milliseconds=duration_ms),
                "duration_ms": duration_ms,
                "error_code": "egress_blocked" if failed else None,
                "error_message": (
                    "Egress destination not in the workspace allowlist."
                    if failed
                    else None
                ),
            },
        )
        # Spans, so the Traces view has something to group. The count varies per
        # run because a trace listing where every row reports the same span
        # count reads as generated rather than observed.
        span_count = 3 + (index % 6)
        for order in range(span_count):
            _upsert(
                db,
                RunStep,
                _sid("step", ctx, f"{suffix}:{order}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "run_id": run_id,
                    "step_id": f"step-{order}",
                    "step_type": ("agent_plan", "retrieval", "tool")[order % 3],
                    "status": "failed"
                    if failed and order == span_count - 1
                    else "succeeded",
                    "started_at": started,
                    "ended_at": started + timedelta(milliseconds=duration_ms),
                    "metrics_json": _meta(latency_ms=duration_ms // span_count),
                },
            )
        ids.append(run_id)
    db.commit()
    return ids


# --------------------------------------------------------------------------- #
# threads -- chat.html
# --------------------------------------------------------------------------- #

THREADS: list[tuple[str, str, str, int]] = [
    (
        "checkout-api 502s",
        "ops-copilot",
        "tailing error logs from the restarted pods",
        0,
    ),
    (
        "staging deploy window",
        "ops-copilot",
        "window confirmed 14:00–15:00Z, freeze after",
        2,
    ),
    (
        "quota report for finance",
        "ops-copilot",
        "exported usage by team as a run artifact",
        4,
    ),
    (
        "vault rotation runbook",
        "support-triage",
        "SLACK_BOT_TOKEN rotated · 3 agents re-bound",
        26,
    ),
    (
        "gpu-01 disk pressure",
        "support-triage",
        "cleared 42 GB of stale model shards",
        30,
    ),
]


def _seed_threads(db, ctx: RequestContext, agents: dict[str, str]) -> list[str]:
    now = utc_now()
    ids: list[str] = []
    for title, agent_key, summary, hours_ago in THREADS:
        thread_id = _sid("thr", ctx, title)
        at = now - timedelta(hours=hours_ago)
        _upsert(
            db,
            Thread,
            thread_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agents.get(agent_key),
                "title": title,
                "status": "active",
                "thread_type": "chat",
                "source": "console",
                "owner_user_id": ctx.user_id,
                "summary": summary,
                "default_model_ref": "model:anthropic:claude-sonnet-5",
                "message_count": 2,
                "last_message_at": at,
                "last_user_message_at": at,
                "last_assistant_message_at": at,
                "metadata_json": _meta(),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        for order, (role, text) in enumerate((("user", title), ("assistant", summary))):
            _upsert(
                db,
                ThreadMessage,
                _sid("msg", ctx, f"{title}:{role}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "thread_id": thread_id,
                    "sequence_no": order,
                    "role": role,
                    "content": text,
                    "message_type": "text",
                    "status": "completed",
                    "content_json": {"type": "text", "text": text},
                    "created_by": ctx.user_id,
                    "created_at": at,
                },
            )
        ids.append(thread_id)
    db.commit()
    return ids


# --------------------------------------------------------------------------- #
# tasks and approvals -- tasks.html, approvals.html
# --------------------------------------------------------------------------- #

TASKS: list[dict[str, Any]] = [
    ("invoice-reconcile", "monthly close", "wf.batch", "waiting_approval", 6, 7),
    ("churn-signal-scan", "Q3 backfill", "agent.batch", "running", 41, 100),
    ("docs-nightly-sync", "full re-embed", "wf.batch", "running", 88, 100),
    ("evidence-export", "2026-07 bundle", "evidence.export", "queued", 0, 1),
    ("quota-report", "weekly finance digest", "agent.run", "queued", 0, 1),
    ("evidence-verify", "2026-07 signature check", "evidence.export", "queued", 0, 1),
    ("release-digest", "week 35 workflow run", "wf.run", "succeeded", 5, 5),
    ("billing-audit", "hourly reconciliation", "agent.run", "failed", 2, 8),
]


def _seed_tasks(
    db, ctx: RequestContext, agents: dict[str, str], task_count: int
) -> list[str]:
    now = utc_now()
    ids: list[str] = []
    for offset, (name, note, task_type, status, done, total) in enumerate(TASKS):
        task_id = _sid("task", ctx, name)
        started = now - timedelta(minutes=9 * (offset + 1))
        _upsert(
            db,
            Task,
            task_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agents.get(name),
                "task_type": task_type,
                "status": status,
                "input_json": _meta(name=name, note=note),
                "output_json": {}
                if status != "succeeded"
                else {"summary": f"{name} finished"},
                "progress_json": {"completed": done, "total": total},
                "error_code": "step_failed" if status == "failed" else None,
                "error_message": (
                    "Egress destination not in the workspace allowlist."
                    if status == "failed"
                    else None
                ),
                "started_at": None if status == "queued" else started,
                "finished_at": started if status in {"succeeded", "failed"} else None,
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        ids.append(task_id)

    # Filler tasks so the panel's task count matches what the page lists.
    for index in range(len(TASKS), max(len(TASKS), task_count)):
        name = f"scheduled-batch-{index:03d}"
        task_id = _sid("task", ctx, name)
        started = now - timedelta(hours=index)
        _upsert(
            db,
            Task,
            task_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": None,
                "task_type": "agent.run",
                "status": "succeeded",
                "input_json": _meta(name=name),
                "output_json": {"summary": f"{name} finished"},
                "progress_json": {"completed": 1, "total": 1},
                "error_code": None,
                "error_message": None,
                "started_at": started,
                "finished_at": started + timedelta(minutes=3),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        ids.append(task_id)
    db.commit()
    return ids


APPROVALS: list[tuple[str, str, str, int]] = [
    (
        "Post 14 journal entries to the ledger",
        "finance.journal.post",
        "billing-audit",
        72,
    ),
    (
        "Scale checkout-api to 16 replicas",
        "infra.scale.prod",
        "ops-copilot",
        18,
    ),
]


def _seed_approvals(db, ctx: RequestContext, agents: dict[str, str]) -> list[str]:
    now = utc_now()
    ids: list[str] = []
    for title, policy_ref, agent_key, minutes_ago in APPROVALS:
        approval_id = _sid("apr", ctx, title)
        _upsert(
            db,
            ApprovalRequest,
            approval_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agents.get(agent_key),
                "title": title,
                "policy_ref": policy_ref,
                "status": "pending",
                "details_json": _meta(requested_by=agent_key),
                "requested_by": ctx.user_id,
                "created_at": now - timedelta(minutes=minutes_ago),
            },
        )
        ids.append(approval_id)
    db.commit()
    return ids


AUDITS: list[tuple[str, str, str, bool]] = [
    ("secret_rotate", "secrets.rotate", "vault:SLACK_BOT_TOKEN", True),
    ("egress_deny", "egress.deny", "https://paste.example.net", False),
    ("policy_activate", "policy.activate", "v2026.08.27-2", True),
]


def _seed_audits(db, ctx: RequestContext, run_ids: list[str]) -> None:
    # The audit list only returns events attached to a run: with no run_id the
    # Govern > Audit log page stays empty however many events exist.
    for index, (key, operation, target, allowed) in enumerate(AUDITS):
        run_id = run_ids[index % len(run_ids)] if run_ids else None
        _upsert(
            db,
            AuditEvent,
            _sid("aud", ctx, key),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "event_type": "security.policy",
                "resource_type": "security",
                "resource_id": key,
                "run_id": run_id,
                "trace_id": f"{TRACE_PREFIX}{key}",
                "outcome": "allow" if allowed else "deny",
                "operation": operation,
                "actor_user_id": ctx.user_id,
                "scope": "workspace",
                "payload_json": _meta(allowed=allowed, target=target),
            },
        )
    db.commit()


#: What each model charged per million tokens in the prototype's pricing table.
MODEL_PRICING: list[tuple[str, str, float, float]] = [
    ("model:anthropic:claude-sonnet-5", "anthropic", 3.00, 15.00),
    ("model:anthropic:claude-haiku-4.5", "anthropic", 1.00, 5.00),
    ("model:dashscope:qwen3-235b", "dashscope", 0.90, 2.40),
]


def _seed_costs(db, ctx: RequestContext, run_ids: list[str]) -> list[str]:
    """One cost entry per run, so the Runs page can total tokens and spend."""
    now = utc_now()
    ids: list[str] = []
    for index, run_id in enumerate(run_ids):
        model_ref, provider_kind, prompt_rate, completion_rate = MODEL_PRICING[
            index % len(MODEL_PRICING)
        ]
        prompt_tokens = 1800 + (index % 50) * 60
        completion_tokens = 400 + (index % 30) * 25
        amount = Decimal(
            str(
                round(
                    prompt_tokens / 1_000_000 * prompt_rate
                    + completion_tokens / 1_000_000 * completion_rate,
                    6,
                )
            )
        )
        entry_id = _sid("cost", ctx, run_id)
        _upsert(
            db,
            RunCostEntry,
            entry_id,
            {
                "run_id": run_id,
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "currency": "USD",
                "amount": amount,
                "pricing_snapshot_json": _meta(
                    prompt_per_million=prompt_rate,
                    completion_per_million=completion_rate,
                ),
                "billing_basis": "tokens",
                "billed_quantity": Decimal(prompt_tokens + completion_tokens),
                "provider_kind": provider_kind,
                "provider": provider_kind,
                "model_ref": model_ref,
                "operation": "chat.completion",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": 900 + (index % 40) * 120,
                "request_count": 1,
                "created_at": now - timedelta(minutes=index % 1440),
            },
        )
        ids.append(entry_id)
    db.commit()
    return ids


# --------------------------------------------------------------------------- #
# workspace people, keys, credits and egress -- settings.html, policies.html
# --------------------------------------------------------------------------- #

#: The owner already exists from ``_ensure_context``; these are the rest of the
#: team the prototype's Settings page lists.
TEAMMATES: list[tuple[str, str, str]] = [
    ("wei@acme.io", "Wei", "Admin"),
    ("ming@acme.io", "Ming", "Dev"),
    ("dana@acme.io", "Dana", "Viewer"),
]


def _unusable_hash() -> str:
    """A hash no plaintext in this repository can produce.

    Seeded users and API keys are display objects. Hashing a constant would put
    a working credential into every database this script touches, because the
    constant is right here in the source -- so the digest is taken over fresh
    random bytes and nothing can authenticate against it.
    """
    return hashlib.sha256(pysecrets.token_bytes(32)).hexdigest()


def _seed_team(db, ctx: RequestContext) -> list[str]:
    ids: list[str] = []
    for email, name, role in TEAMMATES:
        user_id = _sid("u", ctx, email)
        existing = db.get(User, user_id)
        _upsert(
            db,
            User,
            user_id,
            {
                "email": email,
                "name": name,
                # Keep any existing hash rather than rotating it on every re-seed.
                "password_hash": existing.password_hash
                if existing
                else _unusable_hash(),
                "is_active": True,
                "profile_json": _meta(),
            },
        )
        for model, values in (
            (
                TenantMembership,
                {"tenant_id": ctx.tenant_id, "user_id": user_id, "role": role},
            ),
            (
                WorkspaceMembership,
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "user_id": user_id,
                    "role": role,
                },
            ),
        ):
            # Composite primary keys, so merge rather than the id-keyed upsert.
            db.merge(model(**values))
        ids.append(user_id)
    db.commit()
    return ids


API_KEYS: list[tuple[str, str, list[str]]] = [
    ("ci-pipeline", "soit_ci", ["runs:write", "workflows:read"]),
    ("grafana-export", "soit_gr", ["runs:read", "observe:read"]),
    ("partner-sandbox", "soit_ps", ["agents:read"]),
]


def _seed_api_keys(db, ctx: RequestContext) -> list[str]:
    now = utc_now()
    ids: list[str] = []
    for index, (name, prefix, scopes) in enumerate(API_KEYS):
        key_id = _sid("ak", ctx, name)
        existing = db.get(ApiKey, key_id)
        _upsert(
            db,
            ApiKey,
            key_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "user_id": ctx.user_id,
                "name": name,
                "key_prefix": prefix,
                # See _unusable_hash: a seeded key has to be unusable, not merely
                # unpublished.
                "key_hash": existing.key_hash if existing else _unusable_hash(),
                "status": "active",
                "scopes_json": scopes,
                "expires_at": now + timedelta(days=90 - index * 20),
                "last_used_at": now - timedelta(hours=index * 5 + 1),
            },
        )
        ids.append(key_id)
    db.commit()
    return ids


def _seed_credits(db, ctx: RequestContext, cost_entry_ids: list[str]) -> None:
    """A grant and a month of consumption, matching the billing tiles.

    The schema refuses a deduction that names no cost entry, so the spend line
    points at a real one rather than floating free.
    """
    now = utc_now()
    rows = [
        (
            "grant",
            "grant",
            Decimal("4212.40"),
            Decimal("4212.40"),
            "annual allocation",
            None,
        )
    ]
    if cost_entry_ids:
        rows.append(
            (
                "spend",
                "deduction",
                Decimal("-612.40"),
                Decimal("612.40"),
                "model spend this month",
                cost_entry_ids[0],
            )
        )
    for key, kind, delta, amount, note, cost_entry_id in rows:
        _upsert(
            db,
            CreditLedgerEntry,
            _sid("cle", ctx, key),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "kind": kind,
                "credits_delta": delta,
                "cost_entry_id": cost_entry_id,
                "currency": "USD",
                "amount": amount,
                "conversion_snapshot_json": _meta(),
                "note": note,
                "created_by": ctx.user_id,
                "created_at": now - timedelta(days=1),
            },
        )
    db.commit()


def _seed_egress(db, ctx: RequestContext) -> None:
    """Egress rules live on the workspace row, which the Policies page reads."""
    workspace = db.get(Workspace, ctx.workspace_id)
    if workspace is None:
        return
    workspace.egress_allowlist = [
        "https://api.anthropic.com",
        "https://tickets.acme.io",
        "https://docs.acme.io",
    ]
    workspace.egress_blocklist = ["https://paste.example.net"]
    workspace.updated_at = utc_now()
    db.add(workspace)
    db.commit()


# --------------------------------------------------------------------------- #
# entrypoint
# --------------------------------------------------------------------------- #


async def seed_console_prototype(db, args: argparse.Namespace) -> PrototypeSeedSummary:
    ctx = _ensure_context(db, args)
    if args.reset:
        _reset(db, ctx)

    model_refs = _seed_modelhub(db, ctx)
    knowledge = _seed_knowledge(db, ctx)
    workflows = _seed_workflows(db, ctx)

    knowledge_by_key = {
        spec["key"]: item.id for spec, item in zip(KNOWLEDGE, knowledge, strict=False)
    }
    workflow_by_key = {
        spec["key"]: item.id for spec, item in zip(WORKFLOWS, workflows, strict=False)
    }

    agents = _seed_agents(db, ctx, knowledge_by_key, workflow_by_key)
    agent_by_key = {
        spec["key"]: item.id for spec, item in zip(AGENTS, agents, strict=False)
    }

    plugin_ids = _seed_plugins(db, ctx)
    secret_ids = _seed_secrets(db, ctx)
    thread_ids = _seed_threads(db, ctx, agent_by_key)
    run_ids = _seed_runs(db, ctx, agent_by_key, args.runs)
    task_ids = _seed_tasks(db, ctx, agent_by_key, args.tasks)
    approval_ids = _seed_approvals(db, ctx, agent_by_key)
    _seed_audits(db, ctx, run_ids)
    cost_entry_ids = _seed_costs(db, ctx, run_ids)
    _seed_team(db, ctx)
    _seed_api_keys(db, ctx)
    _seed_credits(db, ctx, cost_entry_ids)
    _seed_egress(db, ctx)

    return PrototypeSeedSummary(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        agent_ids=[item.id for item in agents],
        workflow_ids=[item.id for item in workflows],
        knowledge_ids=[item.id for item in knowledge],
        plugin_ids=plugin_ids,
        model_refs=model_refs,
        secret_ids=secret_ids,
        thread_ids=thread_ids,
        run_ids=run_ids,
        task_ids=task_ids,
        approval_ids=approval_ids,
    )


def main() -> int:
    args = _parse_args()
    db = get_db_sync()
    try:
        summary = asyncio.run(seed_console_prototype(db, args))
        payload = json.dumps(summary.model_dump(), indent=2, sort_keys=True)
        if args.json_output:
            with open(args.json_output, "w", encoding="utf-8") as handle:
                handle.write(payload)
        print(payload)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
