"""Seed extended Enterprise MVP scenario data for local demonstrations."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import and_, select

from app.infra.db.session import get_db_sync
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.modules.agent.domain.models import (
    Agent,
    AgentBinding,
    AgentPublish,
    AgentVersion,
)
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeIngestTask,
)
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.modules.observe.domain.models import ApprovalRequest, RunFeedback
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginRelease,
    PluginVersion,
)
from app.modules.secrets.domain.models import Secret
from app.modules.workflow.domain.models import (
    Workflow,
    WorkflowPublish,
    WorkflowRun,
    WorkflowVersion,
)
from scripts.bootstrap_enterprise_mvp import BootstrapResult, bootstrap_enterprise_mvp

SEED_SOURCE = "enterprise_mvp_scenarios"
TRACE_PREFIX = f"trace:{SEED_SOURCE}:"


class ScenarioSeedSummary(BaseModel):
    """Stable output index for seeded MVP scenario data."""

    tenant_id: str
    workspace_id: str
    user_id: str
    profile: str
    agent_ids: list[str] = Field(default_factory=list)
    thread_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    workflow_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    provider_ids: list[str] = Field(default_factory=list)
    model_refs: list[str] = Field(default_factory=list)
    plugin_refs: list[str] = Field(default_factory=list)
    secret_ids: list[str] = Field(default_factory=list)
    citation_sources: list[str] = Field(default_factory=list)
    agent_chain_refs: list[dict[str, Any]] = Field(default_factory=list)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed extended Enterprise MVP scenario data.")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="12345678")
    parser.add_argument("--name", default="Test User")
    parser.add_argument("--tenant-name", default="default")
    parser.add_argument("--workspace-name", default="default")
    parser.add_argument("--profile", choices=["broad", "stress"], default="broad")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--json-output", default=None)
    return parser.parse_args()


def _unwrap(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, tuple):
        return row[0]
    try:
        return row[0]
    except Exception:
        return row


def _one(db, query):
    return _unwrap(db.exec(query).first())


def _seed_id(prefix: str, ctx: RequestContext, key: str) -> str:
    digest = hashlib.sha1(f"{ctx.tenant_id}:{ctx.workspace_id}:{key}".encode()).hexdigest()[:16]
    return f"{prefix}_seed_{digest}"


def _seed_meta(**extra: Any) -> dict[str, Any]:
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


def _scoped_query(model: type[Any], ctx: RequestContext):
    return select(model).where(and_(model.tenant_id == ctx.tenant_id, model.workspace_id == ctx.workspace_id))


def _dict_has_seed(value: Any) -> bool:
    return isinstance(value, dict) and value.get("seed_source") == SEED_SOURCE


def _delete_items(db, items: Iterable[Any]) -> None:
    for item in items:
        db.delete(item)


def _reset_seed_data(db, ctx: RequestContext) -> None:
    seed_runs = [
        _unwrap(row)
        for row in db.exec(_scoped_query(Run, ctx)).all()
        if str(_unwrap(row).trace_id or "").startswith(TRACE_PREFIX)
        or str(_unwrap(row).id).startswith("run_seed_")
    ]
    seed_run_ids = [run.id for run in seed_runs]

    for model in (RunCostEntry, RunArtifact, RunStep):
        if seed_run_ids:
            _delete_items(db, [_unwrap(row) for row in db.exec(select(model).where(model.run_id.in_(seed_run_ids))).all()])

    if seed_run_ids:
        _delete_items(db, [_unwrap(row) for row in db.exec(select(ResponseEvent).where(ResponseEvent.run_id.in_(seed_run_ids))).all()])
        _delete_items(db, [_unwrap(row) for row in db.exec(select(Response).where(Response.run_id.in_(seed_run_ids))).all()])
        _delete_items(db, [_unwrap(row) for row in db.exec(select(WorkflowRun).where(WorkflowRun.run_id.in_(seed_run_ids))).all()])
        _delete_items(db, [_unwrap(row) for row in db.exec(select(ApprovalRequest).where(ApprovalRequest.run_id.in_(seed_run_ids))).all()])
        _delete_items(db, [_unwrap(row) for row in db.exec(select(RunFeedback).where(RunFeedback.run_id.in_(seed_run_ids))).all()])
    _delete_items(db, seed_runs)

    seed_tasks = [
        _unwrap(row)
        for row in db.exec(_scoped_query(Task, ctx)).all()
        if _dict_has_seed(_unwrap(row).input_json) or str(_unwrap(row).id).startswith("task_seed_")
    ]
    seed_task_ids = [task.id for task in seed_tasks]
    if seed_task_ids:
        _delete_items(db, [_unwrap(row) for row in db.exec(select(TaskCheckpoint).where(TaskCheckpoint.task_id.in_(seed_task_ids))).all()])
        _delete_items(db, [_unwrap(row) for row in db.exec(select(TaskEvent).where(TaskEvent.task_id.in_(seed_task_ids))).all()])
    _delete_items(db, seed_tasks)

    seed_threads = [
        _unwrap(row)
        for row in db.exec(_scoped_query(Thread, ctx)).all()
        if _dict_has_seed(_unwrap(row).metadata_json) or str(_unwrap(row).id).startswith("thread_seed_")
    ]
    seed_thread_ids = [thread.id for thread in seed_threads]
    if seed_thread_ids:
        _delete_items(db, [_unwrap(row) for row in db.exec(select(ThreadMessage).where(ThreadMessage.thread_id.in_(seed_thread_ids))).all()])
    _delete_items(db, seed_threads)

    for model, field_name in (
        (KnowledgeChunk, "source_meta_json"),
        (KnowledgeIngestTask, "payload_json"),
        (KnowledgeDocument, "parse_meta_json"),
        (KnowledgeIndex, "index_params_json"),
        (Knowledge, "settings_json"),
    ):
        _delete_items(
            db,
            [
                _unwrap(row)
                for row in db.exec(_scoped_query(model, ctx)).all()
                if _dict_has_seed(getattr(_unwrap(row), field_name, None)) or str(_unwrap(row).id).startswith(("knw_seed_", "doc_seed_", "chunk_seed_", "idx_seed_", "ingest_seed_"))
            ],
        )

    for model, field_name in (
        (PluginInstalledArtifact, "metadata_json"),
        (PluginInstallation, "config_json"),
        (PluginRelease, "notes"),
        (PluginVersion, "metadata_json"),
        (Plugin, "metadata_json"),
    ):
        rows = []
        for row in db.exec(_scoped_query(model, ctx)).all():
            item = _unwrap(row)
            value = getattr(item, field_name, None)
            if _dict_has_seed(value) or value == SEED_SOURCE or str(item.id).startswith(("plg_seed_", "plgv_seed_", "plgr_seed_", "inst_seed_", "plga_seed_")):
                rows.append(item)
        _delete_items(db, rows)

    for model, field_name in (
        (AgentBinding, "config_json"),
        (AgentPublish, "notes"),
        (AgentVersion, "spec_json"),
        (Agent, "profile_json"),
        (WorkflowPublish, "notes"),
        (WorkflowVersion, "spec_json"),
        (Workflow, "metadata_json"),
        (ProviderModel, "config_json"),
        (Provider, "sync_policy_json"),
    ):
        rows = []
        for row in db.exec(_scoped_query(model, ctx)).all():
            item = _unwrap(row)
            value = getattr(item, field_name, None)
            if _dict_has_seed(value) or value == SEED_SOURCE or str(item.id).startswith(("agt_seed_", "agtv_seed_", "agtb_seed_", "agtp_seed_", "wf_seed_", "wfv_seed_", "wfp_seed_", "prov_seed_", "pmdl_seed_")):
                rows.append(item)
        _delete_items(db, rows)

    _delete_items(
        db,
        [
            _unwrap(row)
            for row in db.exec(_scoped_query(Secret, ctx)).all()
            if str(_unwrap(row).id).startswith("sec_seed_") or (SEED_SOURCE in str(_unwrap(row).description or ""))
        ],
    )
    _delete_items(
        db,
        [
            _unwrap(row)
            for row in db.exec(_scoped_query(AuditEvent, ctx)).all()
            if _dict_has_seed(_unwrap(row).payload_json) or str(_unwrap(row).id).startswith("aud_seed_")
        ],
    )
    db.commit()


def _ensure_agent(
    db,
    ctx: RequestContext,
    key: str,
    name: str,
    category: str,
    knowledge_ids: list[str],
    workflow_ids: list[str],
    *,
    tool_refs: list[str] | None = None,
    skill_refs: list[str] | None = None,
) -> Agent:
    agent_id = _seed_id("agt", ctx, key)
    version_id = _seed_id("agtv", ctx, key)
    now = utc_now()
    resolved_tool_refs = list(dict.fromkeys(tool_refs or ["builtin.ticket.create_review_ticket"]))
    resolved_skill_refs = list(dict.fromkeys(skill_refs or []))
    agent = _upsert(
        db,
        Agent,
        agent_id,
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "name": name,
            "description": f"Seeded MVP scenario agent for {category}.",
            "status": "active",
            "visibility": "workspace",
            "category": category,
            "featured": True,
            "tags": ["enterprise", "mvp", "scenario", category],
            "profile_json": _seed_meta(scenario=key, persona=category),
            "instructions_json": {"system_prompt": f"Handle {category} requests with evidence and workflow handoff."},
            "execution_policy_json": {"max_iterations": 4, "require_citations": True},
            "runtime_config_json": {"rag_top_k": 3, "tool_timeout_ms": 5000},
            "default_model_ref": "model:test:agent",
            "current_version_id": version_id,
            "published_version_id": version_id,
            "created_by": ctx.user_id,
            "updated_by": ctx.user_id,
            "published_at": now,
        },
    )
    bindings = {
        "model_ref": "model:test:agent",
        "knowledge_refs": [f"knowledge:{item}" for item in knowledge_ids],
        "tool_refs": resolved_tool_refs,
        "workflow_refs": [f"wf:{item}" for item in workflow_ids],
        "skill_refs": resolved_skill_refs,
    }
    spec = _seed_meta(
        name=name,
        runtime="agent_runtime_v1",
        system_prompt=f"Handle {category} requests with evidence and workflow handoff.",
        temperature=0.1,
        bindings=bindings,
        limits={"max_iterations": 4, "max_tool_calls": 8, "max_llm_calls": 12},
        policies={"require_citations": True},
    )
    _upsert(
        db,
        AgentVersion,
        version_id,
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "agent_id": agent_id,
            "version": 1,
            "status": "published",
            "spec_schema": "agent.v1",
            "spec_json": spec,
            "checksum": hashlib.sha256(json.dumps(spec, sort_keys=True).encode("utf-8")).hexdigest(),
            "created_by": ctx.user_id,
        },
    )
    _upsert(
        db,
        AgentPublish,
        _seed_id("agtp", ctx, key),
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "scope": "workspace",
            "status": "published",
            "notes": SEED_SOURCE,
            "created_by": ctx.user_id,
        },
    )
    binding_specs: list[tuple[str, str | None, str, dict[str, Any]]] = [
        ("model", None, bindings["model_ref"], _seed_meta()),
    ]
    for knowledge_id in knowledge_ids:
        binding_specs.append(("knowledge", knowledge_id, f"knowledge:{knowledge_id}", _seed_meta(top_k=3)))
    for workflow_id in workflow_ids:
        binding_specs.append(("workflow", workflow_id, f"wf:{workflow_id}", _seed_meta()))
    for tool_ref in resolved_tool_refs:
        binding_specs.append(("tool", None, tool_ref, _seed_meta()))
    for skill_ref in resolved_skill_refs:
        binding_specs.append(("skill", None, skill_ref, _seed_meta()))

    for index, (binding_type, target_id, target_key, config_json) in enumerate(binding_specs):
        _upsert(
            db,
            AgentBinding,
            _seed_id("agtb", ctx, f"{key}:{binding_type}:{target_key}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agent_id,
                "agent_version_id": version_id,
                "binding_type": binding_type,
                "target_id": target_id,
                "target_key": target_key,
                "config_json": config_json,
                "sort_order": index,
            },
        )
    db.commit()
    db.refresh(agent)
    return agent


def _ensure_knowledge(db, ctx: RequestContext) -> tuple[list[Knowledge], dict[str, KnowledgeDocument], list[str]]:
    now = utc_now()
    specs = [
        (
            "refund",
            "MVP Refund Policy KB",
            "Refund Policy",
            "refund-policy.md",
            "Refund escalations require account verification, order status review, and a review ticket before approval.",
            "succeeded",
        ),
        (
            "sla",
            "MVP Support SLA KB",
            "Support SLA",
            "support-sla.md",
            "Priority one incidents require a response within fifteen minutes and hourly customer updates.",
            "succeeded",
        ),
        (
            "contract",
            "MVP Contract Approval KB",
            "Contract Approval",
            "contract-approval.md",
            "Contracts above 50000 USD require legal approval, finance approval, and executive sign-off.",
            "succeeded",
        ),
        (
            "invoice",
            "MVP Invoice FAQ KB",
            "Invoice FAQ",
            "invoice-faq.md",
            "\n".join([f"FAQ {idx}: invoice disputes must include PO, invoice id, and billing contact." for idx in range(1, 12)]),
            "succeeded",
        ),
        (
            "failed_sources",
            "MVP Failed Source KB",
            "Crawler and API failures",
            "empty-policy.md",
            "",
            "failed",
        ),
    ]
    knowledge_items: list[Knowledge] = []
    documents: dict[str, KnowledgeDocument] = {}
    citation_sources: list[str] = []
    for key, name, title, filename, text, ingest_status in specs:
        knowledge_id = _seed_id("knw", ctx, key)
        index_id = _seed_id("idx", ctx, key)
        doc_id = _seed_id("doc", ctx, f"{key}:doc")
        chunk_id = _seed_id("chunk", ctx, f"{key}:chunk:0")
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        has_text = bool(text)
        knowledge = _upsert(
            db,
            Knowledge,
            knowledge_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": name,
                "type": "document",
                "description": f"Seeded scenario knowledge base: {title}.",
                "status": "active",
                "visibility": "workspace",
                "settings_json": _seed_meta(source_key=key, source_kind="manual" if has_text else "crawler"),
                "chunking_json": {"chunk_size": 600, "overlap": 80},
                "retrieval_json": {"top_k": 3, "rerank": False},
                "default_embedding_model_ref": "model:test:embedding",
                "default_index_id": index_id,
                "doc_count": 1,
                "chunk_count": 1 if has_text else 0,
                "last_ingested_at": now if ingest_status == "succeeded" else None,
                "last_indexed_at": now if ingest_status == "succeeded" else None,
                "tags": ["enterprise", "mvp", "scenario", key],
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
                "name": f"{key}-primary",
                "is_primary": True,
                "provider": "file-backed",
                "collection_name": f"seed_{knowledge_id}",
                "embedding_model_ref": "model:test:embedding",
                "dimension": 3,
                "metric_type": "cosine",
                "index_params_json": _seed_meta(profile="local"),
                "search_params_json": {"top_k": 3},
                "filters_json": {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id},
                "status": "ready" if has_text else "failed",
                "doc_count": 1,
                "chunk_count": 1 if has_text else 0,
                "vector_count": 1 if has_text else 0,
                "last_build_at": now if has_text else None,
                "last_error_code": None if has_text else "empty_document",
                "last_error_message": None if has_text else "Document has no extractable text.",
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        document = _upsert(
            db,
            KnowledgeDocument,
            doc_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "knowledge_id": knowledge_id,
                "doc_key": filename,
                "version": 1,
                "is_latest": True,
                "source_kind": "manual" if has_text else "crawler",
                "source_uri": f"kb://seed/{filename}",
                "title": title,
                "language": "en",
                "mime_type": "text/markdown",
                "filename": filename,
                "size_bytes": len(text.encode("utf-8")),
                "checksum": checksum,
                "content_hash": checksum,
                "status": "indexed" if has_text else "failed",
                "error_code": None if has_text else "empty_document",
                "error_message": None if has_text else "Document has no extractable text.",
                "retry_count": 1 if not has_text else 0,
                "parse_meta_json": _seed_meta(source_key=key, pages=1),
                "index_meta_json": {"index_id": index_id, "chunk_count": 1 if has_text else 0},
                "access_policy_json": {"visibility": "workspace"},
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        _upsert(
            db,
            KnowledgeIngestTask,
            _seed_id("ingest", ctx, f"{key}:ingest"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "knowledge_id": knowledge_id,
                "document_id": doc_id,
                "status": ingest_status,
                "payload_json": _seed_meta(doc_key=filename, scenario=key, source_kind="manual" if has_text else "crawler"),
                "error_code": None if has_text else "empty_document",
                "error_message": None if has_text else "Document has no extractable text.",
                "retry_count": 1 if not has_text else 0,
                "max_retries": 2,
                "started_at": now - timedelta(minutes=12),
                "finished_at": now - timedelta(minutes=10),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        if has_text:
            _upsert(
                db,
                KnowledgeChunk,
                chunk_id,
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "knowledge_id": knowledge_id,
                    "document_id": doc_id,
                    "document_version": 1,
                    "chunk_no": 0,
                    "chunk_key": f"{filename}:1:0",
                    "content_hash": checksum,
                    "text_preview": text[:512],
                    "start_offset": 0,
                    "end_offset": len(text),
                    "section_path": [title],
                    "source_meta_json": _seed_meta(source=filename, document_id=doc_id),
                    "char_count": len(text),
                    "token_count": max(8, len(text.split())),
                    "embedding_model_ref": "model:test:embedding",
                    "vector_ref": f"seed_{knowledge_id}:0",
                    "indexed_at": now,
                    "index_status": "indexed",
                },
            )
            citation_sources.append(filename)
        knowledge_items.append(knowledge)
        documents[key] = document
    db.commit()
    return knowledge_items, documents, citation_sources


def _workflow_spec(key: str, name: str, mode: str) -> dict[str, Any]:
    return _seed_meta(
        name=name,
        mode=mode,
        graph={
            "nodes": [
                {"id": "start", "type": "set_var", "params": {"scenario": key}},
                {"id": "ticket_tool", "type": "tool", "params": {"tool_ref": "builtin.ticket.create_review_ticket"}},
                {"id": "end", "type": "output", "params": {"status": mode}},
            ],
            "edges": [
                {"id": "e1", "from": "start", "to": "ticket_tool"},
                {"id": "e2", "from": "ticket_tool", "to": "end"},
            ],
        },
        inputs_schema={"type": "object", "required": ["customer_message"] if mode != "missing_params" else ["missing"]},
        outputs_schema={"type": "object"},
    )


def _ensure_workflows(db, ctx: RequestContext) -> list[Workflow]:
    specs = [
        ("ticket_success", "MVP Ticket Triage Success", "succeeded"),
        ("missing_params", "MVP Missing Parameter Failure", "missing_params"),
        ("approval_wait", "MVP Approval Gate Wait", "waiting_approval"),
        ("tool_retry", "MVP Tool Retry Recovery", "retry_succeeded"),
        ("long_running", "MVP Long Running Placeholder", "running"),
    ]
    workflows: list[Workflow] = []
    for key, name, mode in specs:
        workflow_id = _seed_id("wf", ctx, key)
        version_id = _seed_id("wfv", ctx, key)
        workflow = _upsert(
            db,
            Workflow,
            workflow_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": name,
                "description": f"Seeded workflow scenario: {mode}.",
                "summary": f"Demonstrates workflow state {mode}.",
                "status": "active",
                "visibility": "workspace",
                "category": "enterprise_mvp",
                "tags": ["enterprise", "mvp", "scenario", mode],
                "owner_user_id": ctx.user_id,
                "metadata_json": _seed_meta(scenario=key, mode=mode),
                "current_version_id": version_id,
                "published_version_id": version_id,
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
                "version": 1,
                "status": "published",
                "spec_schema": "workflow.v1",
                "spec_json": _workflow_spec(key, name, mode),
                "created_by": ctx.user_id,
            },
        )
        _upsert(
            db,
            WorkflowPublish,
            _seed_id("wfp", ctx, key),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "workflow_id": workflow_id,
                "workflow_version_id": version_id,
                "action": "publish",
                "scope": "workspace",
                "status": "published",
                "notes": SEED_SOURCE,
                "created_by": ctx.user_id,
            },
        )
        workflows.append(workflow)
    db.commit()
    return workflows


def _ensure_modelhub(db, ctx: RequestContext) -> tuple[list[str], list[str]]:
    provider_specs = [
        ("stub_active", "MVP Stub Provider", "test", "active", "stub://active"),
        ("stub_degraded", "MVP Degraded Provider", "test", "error", "stub://degraded"),
        ("stub_disabled", "MVP Disabled Provider", "test", "disabled", "stub://disabled"),
    ]
    provider_ids: list[str] = []
    model_refs: list[str] = []
    for key, name, kind, status, base_url in provider_specs:
        provider_id = _seed_id("prov", ctx, key)
        provider = _upsert(
            db,
            Provider,
            provider_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "kind": kind,
                "name": name,
                "base_url": base_url,
                "credential_secret_id": _seed_id("sec", ctx, "provider_key"),
                "status": status,
                "sync_policy_json": _seed_meta(auto_sync=False, scenario=key),
                "last_healthcheck_at": utc_now(),
                "last_healthcheck_error": None if status == "active" else f"Seeded provider status: {status}",
            },
        )
        provider_ids.append(provider.id)
        for model_key, display, model_status in (
            ("agent", "Seed Agent Chat", "active"),
            ("workflow", "Seed Workflow Chat", "active" if status == "active" else "disabled"),
            ("failing", "Seed Failing Model", "disabled" if status == "disabled" else "active"),
        ):
            model_id = f"{key}-{model_key}"
            _upsert(
                db,
                ProviderModel,
                _seed_id("pmdl", ctx, f"{key}:{model_key}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "provider_id": provider.id,
                    "provider_kind": kind,
                    "model_id": model_id,
                    "display_name": display,
                    "description": f"Seeded model scenario {key}/{model_key}.",
                    "capabilities_json": {"chat": True, "tool_calls": model_key == "agent", "embeddings": model_key == "workflow"},
                    "config_json": _seed_meta(scenario=key, model_key=model_key),
                    "context_window": 8192,
                    "max_output_tokens": 1024,
                    "lifecycle_status": "generally_available" if model_status == "active" else "deprecated",
                    "raw_meta": _seed_meta(provider_status=status),
                    "status": model_status,
                    "source": "local",
                    "sync_status": "in_sync" if status == "active" else "error",
                },
            )
            model_refs.append(f"model:{kind}:{model_id}")
    db.commit()
    return provider_ids, model_refs


def _ensure_plugins(db, ctx: RequestContext) -> list[str]:
    plugin_id = _seed_id("plg", ctx, "governed_tools")
    version_id = _seed_id("plgv", ctx, "governed_tools")
    installation_id = _seed_id("inst", ctx, "governed_tools")
    spec_json = {
        "plugin_type": "mixed",
        "exports": {
            "tools": ["seed.ticket.audit", "seed.egress.check"],
            "workflow_nodes": ["seed.approval_gate"],
            "skills": ["seed-support-playbook"],
            "mcp_servers": ["seed-compliance-mcp"],
        },
    }
    manifest_json = {"name": "seed-governed-tools", "version": "1.0.0", "enabled": True}
    _upsert(
        db,
        Plugin,
        plugin_id,
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "name": "seed-governed-tools",
            "version": "1.0.0",
            "publisher": "soit",
            "plugin_type": "mixed",
            "status": "active",
            "description": "Seeded plugin exposing governed tools and compliance capabilities.",
            "spec_json": spec_json,
            "manifest_json": manifest_json,
            "metadata_json": _seed_meta(package="seed-governed-tools"),
            "publish_status": "published",
            "installed_count": 1,
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
            "package_version": "1.0.0",
            "status": "published",
            "spec_schema": "plugin.v1",
            "spec_json": spec_json,
            "manifest_json": manifest_json,
            "artifact_summary_json": spec_json["exports"],
            "metadata_json": _seed_meta(package_sha256="seed"),
            "created_by": ctx.user_id,
        },
    )
    _upsert(
        db,
        PluginRelease,
        _seed_id("plgr", ctx, "governed_tools"),
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "plugin_id": plugin_id,
            "plugin_version_id": version_id,
            "action": "publish",
            "scope": "workspace",
            "status": "published",
            "notes": SEED_SOURCE,
            "created_by": ctx.user_id,
        },
    )
    _upsert(
        db,
        PluginInstallation,
        installation_id,
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "plugin_id": plugin_id,
            "plugin_version_id": version_id,
            "enabled": True,
            "state": "installed",
            "installed_by": ctx.user_id,
            "config_json": _seed_meta(egress_policy="allowlist"),
        },
    )
    artifacts = [
        ("tool", "plugin_tool:seed.ticket.audit", {"tool_spec": {"name": "Ticket Audit Tool"}}),
        ("tool", "plugin_tool:seed.egress.check", {"tool_spec": {"name": "Egress Check Tool"}}),
        ("workflow_node", "plugin_node:seed.approval_gate", {"node_spec": {"name": "Approval Gate Node"}}),
        ("skill", "plugin_skill:seed-support-playbook", {}),
        (
            "mcp_server",
            "mcp_server:seed-compliance-mcp",
            {
                "mcp_server": {
                    "name": "seed-compliance-mcp",
                    "transport": "streamable_http",
                    "endpoint": "https://mcp.soit.local/compliance/mcp",
                    "capabilities_json": {
                        "tools": [{"name": "deny_external_post"}, {"name": "redact_secret_preview"}],
                        "resources": [{"name": "egress_audit_log"}],
                    },
                }
            },
        ),
    ]
    refs: list[str] = []
    for artifact_kind, artifact_ref, metadata in artifacts:
        _upsert(
            db,
            PluginInstalledArtifact,
            _seed_id("plga", ctx, artifact_ref),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "plugin_id": plugin_id,
                "plugin_version_id": version_id,
                "installation_id": installation_id,
                "artifact_kind": artifact_kind,
                "artifact_ref": artifact_ref,
                "artifact_id": artifact_ref.split(":", 1)[-1],
                "state": "enabled",
                "enabled": True,
                "metadata_json": _seed_meta(**metadata),
            },
        )
        refs.append(artifact_ref)
    db.commit()
    return refs


def _ensure_secrets_and_audits(db, ctx: RequestContext) -> list[str]:
    secret_specs = [
        ("provider_key", "Seed Provider API Key"),
        ("ticket_webhook", "Seed Ticket Webhook Token"),
    ]
    secret_ids: list[str] = []
    for key, name in secret_specs:
        secret_id = _seed_id("sec", ctx, key)
        _upsert(
            db,
            Secret,
            secret_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "name": name,
                "description": f"{SEED_SOURCE}: value is intentionally not stored in database responses.",
                "secret_ref": f"secret:{secret_id}",
                "last_rotated_at": utc_now() - timedelta(hours=1),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        secret_ids.append(secret_id)
    for key, operation, allowed in (
        ("egress_allow", "egress.allow", True),
        ("egress_deny", "egress.deny", False),
        ("secret_preview", "secret.preview_redacted", True),
    ):
        _upsert(
            db,
            AuditEvent,
            _seed_id("aud", ctx, key),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "event_type": "security.policy",
                "resource_type": "security",
                "resource_id": key,
                "operation": operation,
                "actor_user_id": ctx.user_id,
                "scope": "workspace",
                "payload_json": _seed_meta(allowed=allowed, target="https://tickets.example.local"),
            },
        )
    db.commit()
    return secret_ids


def _ensure_run(
    db,
    ctx: RequestContext,
    key: str,
    *,
    mode: str,
    kind: str,
    subject_kind: str,
    subject_id: str,
    status: str,
    input_summary: str,
    output_summary: str,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    knowledge_id: str | None = None,
    child_run_id: str | None = None,
    tool_ref: str = "builtin.ticket.create_review_ticket",
    workflow_node_ref: str | None = None,
    audit_decision: str | None = None,
    failed: bool = False,
) -> Run:
    now = utc_now()
    run_id = _seed_id("run", ctx, key)
    ended_at = None if status in {"running", "queued", "waiting_approval"} else now
    run = _upsert(
        db,
        Run,
        run_id,
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
            "trace_id": f"{TRACE_PREFIX}{key}",
            "mode": mode,
            "kind": kind,
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "status": status,
            "input_summary": f"[{SEED_SOURCE}] {input_summary}",
            "output_summary": output_summary,
            "started_at": now - timedelta(minutes=20),
            "ended_at": ended_at,
            "duration_ms": None if ended_at is None else 2400,
            "error_code": "seeded_failure" if failed else None,
            "error_message": "Seeded failure for retry and error UI validation." if failed else None,
        },
    )
    steps = [
        (
            "plan",
            "agent_plan" if subject_kind == "agent" else "io",
            "succeeded",
            {"seed_source": SEED_SOURCE, "latency_ms": 90, "agent_id": agent_id},
        ),
        (
            "retrieve",
            "retrieval",
            "succeeded",
            {
                "seed_source": SEED_SOURCE,
                "knowledge_id": knowledge_id,
                "result_count": 2,
                "citation_count": 2,
                "avg_score": 0.91,
                "latency_ms": 130,
                "agent_id": agent_id,
            },
        ),
        (
            "tool",
            "tool",
            "failed" if failed else "succeeded",
            {
                "seed_source": SEED_SOURCE,
                "latency_ms": 300,
                "retry_count": 1 if failed else 0,
                "agent_id": agent_id,
                "workflow_node_ref": workflow_node_ref,
                "tool_call": {
                    "tool_ref": tool_ref,
                    "tool_name": tool_ref,
                    "tool_type": "plugin" if tool_ref.startswith(("plugin_", "mcp_")) else "builtin",
                    "status": "failed" if failed else "completed",
                    "arguments": {"customer_id": "cust-seed-001", "priority": "high"},
                    "result": {"ticket_id": "TICKET-SEED-001", "workflow_run_id": child_run_id, "status": "created"},
                },
                "audit_json": {
                    "seed_source": SEED_SOURCE,
                    "decision": audit_decision or ("allow" if not failed else "deny"),
                    "policy_ref": "policy:seed-egress",
                    "egress_target": "https://tickets.example.local",
                },
            },
        ),
    ]
    for order, (step_key, step_type, step_status, metrics) in enumerate(steps):
        if step_type == "retrieval" and not knowledge_id:
            continue
        step_id = _seed_id("step", ctx, f"{key}:{step_key}")
        _upsert(
            db,
            RunStep,
            step_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "trace_id": run.trace_id,
                "run_id": run_id,
                "step_id": step_key,
                "step_type": step_type,
                "node_id": step_key if workflow_id else None,
                "status": step_status,
                "input_summary": f"Seeded {step_type} input",
                "output_summary": f"Seeded {step_type} output",
                "metrics_json": metrics,
                "error_code": "seeded_tool_failure" if step_status == "failed" else None,
                "error_message": "Seeded tool failure." if step_status == "failed" else None,
                "started_at": now - timedelta(minutes=20, seconds=-order),
                "ended_at": now - timedelta(minutes=19, seconds=-order),
            },
        )
    _upsert(
        db,
        RunArtifact,
        _seed_id("art", ctx, key),
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "run_id": run_id,
            "step_id": _seed_id("step", ctx, f"{key}:tool"),
            "type": "json",
            "mime": "application/json",
            "size_bytes": 256,
            "sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
            "storage_key": f"seed/{ctx.workspace_id}/{key}.json",
            "meta_json": _seed_meta(scenario=key),
        },
    )
    _upsert(
        db,
        RunCostEntry,
        _seed_id("cost", ctx, key),
        {
            "run_id": run_id,
            "step_id": _seed_id("step", ctx, f"{key}:plan"),
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "currency": "USD",
            "amount": Decimal("0.004200"),
            "billing_basis": "tokens",
            "billed_quantity": Decimal("420"),
            "provider": "test",
            "model_ref": "model:test:agent",
            "source_port": "llm",
            "operation": "chat",
            "prompt_tokens": 300,
            "completion_tokens": 120,
            "total_tokens": 420,
            "latency_ms": 850,
        },
    )
    db.commit()
    db.refresh(run)
    return run


def _ensure_responses_and_threads(
    db,
    ctx: RequestContext,
    *,
    agents: list[Agent],
    knowledge: list[Knowledge],
    documents: dict[str, KnowledgeDocument],
    runs: list[Run],
) -> list[str]:
    citation = {
        "knowledge_id": knowledge[0].id,
        "document_id": documents["refund"].id,
        "chunk_id": _seed_id("chunk", ctx, "refund:chunk:0"),
        "source": "refund-policy.md",
        "source_name": "refund-policy.md",
        "title": "Refund Policy",
        "score": 0.94,
    }
    thread_specs = [
        ("chat_success", "General policy question", None, runs[2].id, "succeeded", [], []),
        ("agent_citation", "Refund escalation with citation", agents[0].id, runs[0].id, "succeeded", [citation], []),
        (
            "attachment",
            "Invoice attachment review",
            agents[1].id,
            runs[2].id,
            "succeeded",
            [],
            [{"filename": "invoice-dispute.txt", "mime_type": "text/plain", "size_bytes": 120}],
        ),
        ("failed_retry", "Failed model call then recovery", agents[0].id, runs[4].id, "active", [citation], []),
        ("approval_wait", "Approval waiting handoff", agents[2].id, runs[3].id, "active", [], []),
    ]
    thread_ids: list[str] = []
    for index, (key, title, agent_id, run_id, status, citations, attachments) in enumerate(thread_specs):
        thread_id = _seed_id("thread", ctx, key)
        response_id = _seed_id("resp", ctx, key)
        _upsert(
            db,
            Thread,
            thread_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agent_id,
                "title": title,
                "status": status,
                "thread_type": "agent" if agent_id else "chat",
                "source": "seed",
                "owner_user_id": ctx.user_id,
                "summary": f"Seeded thread scenario: {key}.",
                "default_model_ref": "model:test:agent",
                "knowledge_config_json": _seed_meta(knowledge_ids=[item.id for item in knowledge[:2]]),
                "tool_config_json": {"tool_refs": ["builtin.ticket.create_review_ticket"]},
                "metadata_json": _seed_meta(scenario=key),
                "latest_run_id": run_id,
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        messages = [
            ("user", f"Please handle the seeded scenario {key}.", "succeeded", None),
            ("assistant", f"Seeded assistant answer for {key}.", "failed" if key == "failed_retry" else "succeeded", "seeded_model_error" if key == "failed_retry" else None),
        ]
        if key == "failed_retry":
            messages.append(("assistant", "Retry succeeded with refund policy citation and ticket handoff.", "succeeded", None))
        for sequence, (role, content, message_status, error_code) in enumerate(messages, start=1):
            _upsert(
                db,
                ThreadMessage,
                _seed_id("msg", ctx, f"{key}:{sequence}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "thread_id": thread_id,
                    "run_id": run_id if role == "assistant" else None,
                    "response_id": response_id if role == "assistant" else None,
                    "sequence_no": sequence,
                    "role": role,
                    "content": content,
                    "message_type": "text",
                    "status": message_status,
                    "content_json": {"text": content},
                    "model_ref": "model:test:agent" if role == "assistant" else None,
                    "tokens_prompt": 200 if role == "assistant" else None,
                    "tokens_completion": 80 if role == "assistant" else None,
                    "finish_reason": "stop" if message_status == "succeeded" and role == "assistant" else None,
                    "citations_json": citations if role == "assistant" else [],
                    "attachments_json": attachments if role == "user" else [],
                    "tool_calls_json": [{"tool_ref": "builtin.ticket.create_review_ticket", "status": "completed"}] if key == "agent_citation" and role == "assistant" else [],
                    "error_code": error_code,
                    "error_message": "Seeded transient model failure." if error_code else None,
                    "metadata_json": _seed_meta(scenario=key),
                    "created_by": ctx.user_id,
                },
            )
        _upsert(
            db,
            Response,
            response_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "thread_id": thread_id,
                "agent_id": agent_id,
                "run_id": run_id,
                "model": "model:test:agent",
                "provider": "test",
                "status": "failed" if key == "failed_retry" else "completed",
                "input_json": _seed_meta(prompt=title),
                "output_json": {"text": f"Seeded response for {key}.", "citations": citations},
                "usage_json": {"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280},
                "metadata_json": _seed_meta(scenario=key),
                "error_code": "seeded_model_error" if key == "failed_retry" else None,
                "error_message": "Seeded transient model failure." if key == "failed_retry" else None,
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
                "completed_at": utc_now(),
            },
        )
        for event_index, event_type in enumerate(("response.created", "message.delta", "response.completed"), start=1):
            _upsert(
                db,
                ResponseEvent,
                _seed_id("revt", ctx, f"{key}:{event_index}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "response_id": response_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "agent_id": agent_id,
                    "sequence": event_index,
                    "type": event_type,
                    "source": "seed",
                    "payload_json": _seed_meta(index=event_index, scenario=key),
                },
            )
        thread_ids.append(thread_id)
        if index == 0:
            db.commit()
    db.commit()
    return thread_ids


def _ensure_tasks_and_workflow_runs(db, ctx: RequestContext, *, runs: list[Run], workflows: list[Workflow], agents: list[Agent], thread_ids: list[str]) -> list[str]:
    task_specs = [
        ("queued", "queued", runs[5].id),
        ("running", "running", runs[3].id),
        ("waiting_input", "waiting_input", runs[3].id),
        ("waiting_approval", "waiting_approval", runs[3].id),
        ("long_running", "running", runs[3].id),
        ("succeeded", "succeeded", runs[0].id),
        ("failed", "failed", runs[4].id),
    ]
    task_ids: list[str] = []
    now = utc_now()
    for key, status, run_id in task_specs:
        task_id = _seed_id("task", ctx, key)
        started_at = now - timedelta(hours=3) if key == "long_running" else now - timedelta(minutes=25)
        finished_at = now - timedelta(minutes=5) if status in {"succeeded", "failed"} else None
        _upsert(
            db,
            Task,
            task_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agents[0].id,
                "thread_id": thread_ids[0] if thread_ids else None,
                "run_id": run_id,
                "task_type": "enterprise_mvp_scenario",
                "status": status,
                "input_json": _seed_meta(scenario=key),
                "output_json": {"result": "seeded"} if status == "succeeded" else {},
                "progress_json": {"percent": 100 if status == "succeeded" else 55 if status == "running" else 0, "scenario": key},
                "error_code": "seeded_task_failure" if status == "failed" else None,
                "error_message": "Seeded failed task for task center validation." if status == "failed" else None,
                "started_at": started_at,
                "finished_at": finished_at,
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        _upsert(
            db,
            TaskCheckpoint,
            _seed_id("chk", ctx, key),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "task_id": task_id,
                "checkpoint_no": 1,
                "status": status,
                "payload_json": _seed_meta(scenario=key, run_id=run_id),
            },
        )
        _upsert(
            db,
            TaskEvent,
            _seed_id("tevt", ctx, key),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "task_id": task_id,
                "event_type": f"task.{status}",
                "payload_json": _seed_meta(scenario=key),
            },
        )
        task_ids.append(task_id)
    for workflow, run in zip(workflows, runs[1:], strict=False):
        _upsert(
            db,
            WorkflowRun,
            _seed_id("wfr", ctx, workflow.id),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "run_id": run.id,
                "workflow_id": workflow.id,
                "status": run.status,
                "total_nodes": 4,
                "completed_nodes": 3 if run.status != "failed" else 1,
                "failed_nodes": 1 if run.status == "failed" else 0,
                "waiting_nodes": 1 if run.status == "waiting_approval" else 0,
            },
        )
    _upsert(
        db,
        ApprovalRequest,
        _seed_id("apr", ctx, "approval_wait"),
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "run_id": runs[3].id,
            "task_id": _seed_id("task", ctx, "waiting_approval"),
            "thread_id": thread_ids[-1] if thread_ids else None,
            "agent_id": agents[-1].id,
            "title": "Seeded contract approval required",
            "policy_ref": "policy:seed-contract-approval",
            "status": "pending",
            "details_json": _seed_meta(amount_usd=75000),
            "requested_by": ctx.user_id,
        },
    )
    _upsert(
        db,
        RunFeedback,
        _seed_id("fbk", ctx, "agent_parent"),
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "run_id": runs[0].id,
            "task_id": _seed_id("task", ctx, "succeeded"),
            "thread_id": thread_ids[1] if len(thread_ids) > 1 else None,
            "agent_id": agents[0].id,
            "rating": 5,
            "category": "demo",
            "comment": "Seeded successful closed-loop run.",
            "metadata_json": _seed_meta(),
            "created_by": ctx.user_id,
        },
    )
    db.commit()
    return task_ids


def _citation_for(ctx: RequestContext, knowledge_id: str, document: KnowledgeDocument) -> dict[str, Any]:
    return {
        "knowledge_id": knowledge_id,
        "document_id": document.id,
        "chunk_id": _seed_id("chunk", ctx, f"{document.doc_key.split('.', 1)[0]}:chunk:0"),
        "source": document.filename or document.doc_key,
        "source_name": document.filename or document.doc_key,
        "title": document.title,
        "score": 0.93,
    }


def _ensure_chain_thread_response(
    db,
    ctx: RequestContext,
    *,
    key: str,
    title: str,
    agent: Agent,
    parent_run: Run,
    task_id: str,
    citations: list[dict[str, Any]],
    plugin_refs: list[str],
) -> str:
    thread_id = _seed_id("thread", ctx, f"chain:{key}")
    response_id = _seed_id("resp", ctx, f"chain:{key}")
    _upsert(
        db,
        Thread,
        thread_id,
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "agent_id": agent.id,
            "title": title,
            "status": "active",
            "thread_type": "agent",
            "source": "seed",
            "owner_user_id": ctx.user_id,
            "summary": f"Seeded complete agent binding chain: {key}.",
            "default_model_ref": "model:test:agent",
            "knowledge_config_json": _seed_meta(knowledge_ids=[item["knowledge_id"] for item in citations]),
            "tool_config_json": {"tool_refs": plugin_refs},
            "metadata_json": _seed_meta(scenario=f"chain:{key}"),
            "latest_run_id": parent_run.id,
            "created_by": ctx.user_id,
            "updated_by": ctx.user_id,
        },
    )
    messages = [
        ("user", f"Run the complete MVP chain for {title}."),
        ("assistant", f"{title} completed with plugin capability, knowledge citation, and workflow handoff evidence."),
    ]
    for sequence, (role, content) in enumerate(messages, start=1):
        _upsert(
            db,
            ThreadMessage,
            _seed_id("msg", ctx, f"chain:{key}:{sequence}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "thread_id": thread_id,
                "run_id": parent_run.id if role == "assistant" else None,
                "task_id": task_id if role == "assistant" else None,
                "response_id": response_id if role == "assistant" else None,
                "sequence_no": sequence,
                "role": role,
                "content": content,
                "message_type": "text",
                "status": "succeeded",
                "content_json": {"text": content},
                "model_ref": "model:test:agent" if role == "assistant" else None,
                "tokens_prompt": 260 if role == "assistant" else None,
                "tokens_completion": 90 if role == "assistant" else None,
                "finish_reason": "stop" if role == "assistant" else None,
                "citations_json": citations if role == "assistant" else [],
                "attachments_json": [],
                "tool_calls_json": [{"tool_ref": ref, "status": "completed"} for ref in plugin_refs if not ref.startswith("plugin_skill:")] if role == "assistant" else [],
                "metadata_json": _seed_meta(scenario=f"chain:{key}"),
                "created_by": ctx.user_id,
            },
        )
    _upsert(
        db,
        Response,
        response_id,
        {
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "thread_id": thread_id,
            "task_id": task_id,
            "agent_id": agent.id,
            "run_id": parent_run.id,
            "model": "model:test:agent",
            "provider": "test",
            "status": "completed",
            "input_json": _seed_meta(prompt=title),
            "output_json": {
                "text": f"{title} completed with replayable evidence.",
                "citations": citations,
                "plugin_capability_refs": plugin_refs,
            },
            "usage_json": {"prompt_tokens": 260, "completion_tokens": 90, "total_tokens": 350},
            "metadata_json": _seed_meta(scenario=f"chain:{key}"),
            "created_by": ctx.user_id,
            "updated_by": ctx.user_id,
            "completed_at": utc_now(),
        },
    )
    for index, event_type in enumerate(("response.created", "tool.call.completed", "response.completed"), start=1):
        _upsert(
            db,
            ResponseEvent,
            _seed_id("revt", ctx, f"chain:{key}:{index}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "response_id": response_id,
                "run_id": parent_run.id,
                "thread_id": thread_id,
                "task_id": task_id,
                "agent_id": agent.id,
                "sequence": index,
                "type": event_type,
                "source": "seed",
                "payload_json": _seed_meta(index=index, scenario=f"chain:{key}", plugin_capability_refs=plugin_refs),
            },
        )
    db.commit()
    return thread_id


def _ensure_agent_chains(
    db,
    ctx: RequestContext,
    *,
    knowledge: list[Knowledge],
    documents: dict[str, KnowledgeDocument],
    workflows: list[Workflow],
) -> tuple[list[Agent], list[dict[str, Any]], list[str], list[str], list[str]]:
    chain_specs = [
        {
            "key": "support_escalation_commander",
            "name": "MVP Support Escalation Commander",
            "category": "support",
            "knowledge_keys": ["refund", "sla"],
            "workflow_index": 0,
            "plugin_refs": ["plugin_tool:seed.ticket.audit", "mcp_tool:seed-compliance-mcp:deny_external_post"],
            "workflow_node_ref": "plugin_node:seed.approval_gate",
            "task_status": "succeeded",
            "audit_decision": "allow",
        },
        {
            "key": "finance_invoice_resolver",
            "name": "MVP Finance Invoice Resolver",
            "category": "finance",
            "knowledge_keys": ["invoice"],
            "workflow_index": 3,
            "plugin_refs": ["plugin_tool:seed.egress.check"],
            "workflow_node_ref": "plugin_node:seed.approval_gate",
            "task_status": "succeeded",
            "audit_decision": "allow",
        },
        {
            "key": "contract_approval_copilot",
            "name": "MVP Contract Approval Copilot",
            "category": "legal",
            "knowledge_keys": ["contract"],
            "workflow_index": 2,
            "plugin_refs": ["plugin_skill:seed-support-playbook"],
            "workflow_node_ref": "plugin_node:seed.approval_gate",
            "task_status": "waiting_approval",
            "audit_decision": "allow",
        },
        {
            "key": "security_egress_reviewer",
            "name": "MVP Security Egress Reviewer",
            "category": "security",
            "knowledge_keys": ["failed_sources"],
            "workflow_index": 1,
            "plugin_refs": ["plugin_tool:seed.egress.check", "mcp_tool:seed-compliance-mcp:deny_external_post"],
            "workflow_node_ref": "plugin_node:seed.approval_gate",
            "task_status": "failed",
            "audit_decision": "deny",
        },
        {
            "key": "it_sla_coordinator",
            "name": "MVP IT SLA Coordinator",
            "category": "it",
            "knowledge_keys": ["sla"],
            "workflow_index": 4,
            "plugin_refs": ["plugin_tool:seed.ticket.audit"],
            "workflow_node_ref": "plugin_node:seed.approval_gate",
            "task_status": "running",
            "audit_decision": "allow",
        },
    ]
    knowledge_by_key = {
        "refund": knowledge[0],
        "sla": knowledge[1],
        "contract": knowledge[2],
        "invoice": knowledge[3],
        "failed_sources": knowledge[4],
    }
    agents: list[Agent] = []
    chain_refs: list[dict[str, Any]] = []
    thread_ids: list[str] = []
    run_ids: list[str] = []
    task_ids: list[str] = []
    now = utc_now()

    for spec in chain_specs:
        key = str(spec["key"])
        selected_knowledge = [knowledge_by_key[item] for item in spec["knowledge_keys"]]
        workflow = workflows[int(spec["workflow_index"])]
        plugin_refs = list(spec["plugin_refs"])
        tool_refs = [ref for ref in plugin_refs if not ref.startswith("plugin_skill:")]
        skill_refs = [ref for ref in plugin_refs if ref.startswith("plugin_skill:")]
        if not tool_refs:
            tool_refs = ["builtin.ticket.create_review_ticket"]
        agent = _ensure_agent(
            db,
            ctx,
            f"chain:{key}",
            str(spec["name"]),
            str(spec["category"]),
            [item.id for item in selected_knowledge],
            [workflow.id],
            tool_refs=tool_refs,
            skill_refs=skill_refs,
        )
        agents.append(agent)

        child_status = "running" if spec["task_status"] == "running" else "failed" if spec["task_status"] == "failed" else "succeeded"
        child_run = _ensure_run(
            db,
            ctx,
            f"chain:{key}:workflow",
            mode="workflow",
            kind="workflow",
            subject_kind="workflow",
            subject_id=workflow.id,
            status=child_status,
            input_summary=f"{spec['name']} child workflow run",
            output_summary=f"Workflow evidence for {spec['name']}.",
            workflow_id=workflow.id,
            knowledge_id=selected_knowledge[0].id,
            tool_ref=tool_refs[0],
            workflow_node_ref=str(spec["workflow_node_ref"]),
            audit_decision=str(spec["audit_decision"]),
            failed=spec["task_status"] == "failed",
        )
        parent_status = "running" if spec["task_status"] == "running" else "failed" if spec["task_status"] == "failed" else "waiting_approval" if spec["task_status"] == "waiting_approval" else "succeeded"
        parent_run = _ensure_run(
            db,
            ctx,
            f"chain:{key}:parent",
            mode="agent",
            kind="agent",
            subject_kind="agent",
            subject_id=agent.id,
            status=parent_status,
            input_summary=f"{spec['name']} complete binding chain",
            output_summary=f"Agent chain evidence for {spec['name']}.",
            agent_id=agent.id,
            workflow_id=workflow.id,
            knowledge_id=selected_knowledge[0].id,
            child_run_id=child_run.id,
            tool_ref=tool_refs[0],
            workflow_node_ref=str(spec["workflow_node_ref"]),
            audit_decision=str(spec["audit_decision"]),
            failed=spec["task_status"] == "failed",
        )
        task_id = _seed_id("task", ctx, f"chain:{key}")
        task_status = str(spec["task_status"])
        _upsert(
            db,
            Task,
            task_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agent.id,
                "thread_id": _seed_id("thread", ctx, f"chain:{key}"),
                "run_id": parent_run.id,
                "task_type": "enterprise_mvp_agent_chain",
                "status": task_status,
                "input_json": _seed_meta(scenario=f"chain:{key}", plugin_capability_refs=plugin_refs),
                "output_json": {"workflow_run_id": child_run.id, "plugin_capability_refs": plugin_refs},
                "progress_json": {
                    "percent": 100 if task_status == "succeeded" else 60 if task_status == "running" else 20,
                    "scenario": f"chain:{key}",
                },
                "error_code": "seeded_agent_chain_failure" if task_status == "failed" else None,
                "error_message": "Seeded egress denial for agent chain validation." if task_status == "failed" else None,
                "started_at": now - timedelta(minutes=35),
                "finished_at": None if task_status in {"running", "waiting_approval"} else now - timedelta(minutes=5),
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        _upsert(
            db,
            TaskCheckpoint,
            _seed_id("chk", ctx, f"chain:{key}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "task_id": task_id,
                "checkpoint_no": 1,
                "status": task_status,
                "payload_json": _seed_meta(scenario=f"chain:{key}", parent_run_id=parent_run.id, workflow_run_id=child_run.id),
            },
        )
        _upsert(
            db,
            TaskEvent,
            _seed_id("tevt", ctx, f"chain:{key}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "task_id": task_id,
                "event_type": f"agent_chain.{task_status}",
                "payload_json": _seed_meta(scenario=f"chain:{key}", plugin_capability_refs=plugin_refs),
            },
        )
        _upsert(
            db,
            WorkflowRun,
            _seed_id("wfr", ctx, f"chain:{key}"),
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "run_id": child_run.id,
                "workflow_id": workflow.id,
                "status": child_status,
                "total_nodes": 5,
                "completed_nodes": 5 if child_status == "succeeded" else 2,
                "failed_nodes": 1 if child_status == "failed" else 0,
                "waiting_nodes": 1 if parent_status == "waiting_approval" else 0,
            },
        )
        if parent_status == "waiting_approval":
            _upsert(
                db,
                ApprovalRequest,
                _seed_id("apr", ctx, f"chain:{key}"),
                {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "run_id": parent_run.id,
                    "task_id": task_id,
                    "thread_id": _seed_id("thread", ctx, f"chain:{key}"),
                    "agent_id": agent.id,
                    "title": f"{spec['name']} requires approval",
                    "policy_ref": "policy:seed-agent-chain-approval",
                    "status": "pending",
                    "details_json": _seed_meta(plugin_capability_refs=plugin_refs),
                    "requested_by": ctx.user_id,
                },
            )

        citations = [
            _citation_for(ctx, item.id, documents[str(knowledge_key)])
            for item, knowledge_key in zip(selected_knowledge, spec["knowledge_keys"], strict=False)
            if str(knowledge_key) in documents
        ]
        if not citations:
            citations = [
                {
                    "knowledge_id": selected_knowledge[0].id,
                    "document_id": documents["failed_sources"].id,
                    "source": documents["failed_sources"].filename or "empty-policy.md",
                    "source_name": documents["failed_sources"].filename or "empty-policy.md",
                    "title": documents["failed_sources"].title,
                    "score": 0.0,
                }
            ]
        thread_id = _ensure_chain_thread_response(
            db,
            ctx,
            key=key,
            title=str(spec["name"]),
            agent=agent,
            parent_run=parent_run,
            task_id=task_id,
            citations=citations,
            plugin_refs=plugin_refs,
        )
        chain_refs.append(
            {
                "agent_id": agent.id,
                "agent_version_id": agent.published_version_id or agent.current_version_id or "",
                "thread_id": thread_id,
                "parent_run_id": parent_run.id,
                "workflow_run_id": child_run.id,
                "knowledge_ids": [item.id for item in selected_knowledge],
                "workflow_ids": [workflow.id],
                "plugin_capability_refs": plugin_refs,
                "task_id": task_id,
            }
        )
        thread_ids.append(thread_id)
        run_ids.extend([parent_run.id, child_run.id])
        task_ids.append(task_id)
    db.commit()
    return agents, chain_refs, thread_ids, run_ids, task_ids


def _ensure_stress_extras(db, ctx: RequestContext, *, agent_id: str, run_ids: list[str], thread_ids: list[str], task_ids: list[str]) -> None:
    for index in range(20):
        run = _ensure_run(
            db,
            ctx,
            f"stress:{index}",
            mode="chat",
            kind="chat",
            subject_kind="agent",
            subject_id=agent_id,
            status="succeeded" if index % 5 else "failed",
            input_summary=f"Stress scenario {index}",
            output_summary=f"Stress output {index}",
            agent_id=agent_id,
            failed=index % 5 == 0,
        )
        run_ids.append(run.id)
        thread_id = _seed_id("thread", ctx, f"stress:{index}")
        _upsert(
            db,
            Thread,
            thread_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agent_id,
                "title": f"Stress scenario {index}",
                "status": "active",
                "thread_type": "agent",
                "source": "seed",
                "owner_user_id": ctx.user_id,
                "metadata_json": _seed_meta(scenario=f"stress:{index}"),
                "latest_run_id": run.id,
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        thread_ids.append(thread_id)
        task_id = _seed_id("task", ctx, f"stress:{index}")
        _upsert(
            db,
            Task,
            task_id,
            {
                "tenant_id": ctx.tenant_id,
                "workspace_id": ctx.workspace_id,
                "agent_id": agent_id,
                "thread_id": thread_id,
                "run_id": run.id,
                "task_type": "enterprise_mvp_stress",
                "status": "failed" if index % 5 == 0 else "succeeded",
                "input_json": _seed_meta(scenario=f"stress:{index}"),
                "progress_json": {"percent": 100},
                "created_by": ctx.user_id,
                "updated_by": ctx.user_id,
            },
        )
        task_ids.append(task_id)
    db.commit()


async def seed_enterprise_mvp_scenarios(db, args: argparse.Namespace) -> ScenarioSeedSummary:
    bootstrap: BootstrapResult = await bootstrap_enterprise_mvp(db, args)
    ctx = RequestContext(
        tenant_id=bootstrap.tenant_id,
        workspace_id=bootstrap.workspace_id,
        user_id=bootstrap.user_id,
        tenant_role="Owner",
        workspace_role="Owner",
    )
    if args.reset:
        _reset_seed_data(db, ctx)

    knowledge, documents, citation_sources = _ensure_knowledge(db, ctx)
    workflows = _ensure_workflows(db, ctx)
    agents = [
        _ensure_agent(db, ctx, "support_triage", "MVP Support Triage Agent", "support", [knowledge[0].id, knowledge[1].id], [workflows[0].id]),
        _ensure_agent(db, ctx, "finance_ops", "MVP Finance Ops Agent", "finance", [knowledge[3].id], [workflows[3].id]),
        _ensure_agent(db, ctx, "contract_reviewer", "MVP Contract Reviewer Agent", "legal", [knowledge[2].id], [workflows[2].id]),
    ]
    provider_ids, model_refs = _ensure_modelhub(db, ctx)
    plugin_refs = _ensure_plugins(db, ctx)
    secret_ids = _ensure_secrets_and_audits(db, ctx)
    chain_agents, agent_chain_refs, chain_thread_ids, chain_run_ids, chain_task_ids = _ensure_agent_chains(
        db,
        ctx,
        knowledge=knowledge,
        documents=documents,
        workflows=workflows,
    )

    child_workflow_run = _seed_id("run", ctx, "workflow_child")
    runs = [
        _ensure_run(
            db,
            ctx,
            "agent_parent",
            mode="agent",
            kind="agent",
            subject_kind="agent",
            subject_id=agents[0].id,
            status="succeeded",
            input_summary="Refund escalation with knowledge and ticket workflow",
            output_summary="Review ticket created with refund policy citation.",
            agent_id=agents[0].id,
            knowledge_id=knowledge[0].id,
            child_run_id=child_workflow_run,
        ),
        _ensure_run(
            db,
            ctx,
            "workflow_child",
            mode="workflow",
            kind="workflow",
            subject_kind="workflow",
            subject_id=workflows[0].id,
            status="succeeded",
            input_summary="Ticket triage workflow child run",
            output_summary="Ticket tool completed.",
            workflow_id=workflows[0].id,
            knowledge_id=knowledge[0].id,
        ),
        _ensure_run(
            db,
            ctx,
            "chat_success",
            mode="chat",
            kind="chat",
            subject_kind="thread",
            subject_id=_seed_id("thread", ctx, "chat_success"),
            status="succeeded",
            input_summary="General chat success",
            output_summary="Answered with stub model.",
        ),
        _ensure_run(
            db,
            ctx,
            "approval_wait",
            mode="workflow",
            kind="workflow",
            subject_kind="workflow",
            subject_id=workflows[2].id,
            status="waiting_approval",
            input_summary="Contract approval wait",
            output_summary="Waiting for legal approval.",
            workflow_id=workflows[2].id,
            knowledge_id=knowledge[2].id,
        ),
        _ensure_run(
            db,
            ctx,
            "failed_tool",
            mode="agent",
            kind="agent",
            subject_kind="agent",
            subject_id=agents[0].id,
            status="failed",
            input_summary="Tool failure and retry seed",
            output_summary="Seeded failure for Observe failed run UI.",
            agent_id=agents[0].id,
            knowledge_id=knowledge[0].id,
            failed=True,
        ),
        _ensure_run(
            db,
            ctx,
            "queued_summary",
            mode="batch",
            kind="batch",
            subject_kind="task",
            subject_id=_seed_id("task", ctx, "queued"),
            status="queued",
            input_summary="Queued task seed",
            output_summary="Queued for processing center.",
        ),
    ]
    thread_ids = _ensure_responses_and_threads(db, ctx, agents=agents, knowledge=knowledge, documents=documents, runs=runs)
    task_ids = _ensure_tasks_and_workflow_runs(db, ctx, runs=runs, workflows=workflows, agents=agents, thread_ids=thread_ids)
    run_ids = [run.id for run in runs]
    agents.extend(chain_agents)
    thread_ids.extend(chain_thread_ids)
    run_ids.extend(chain_run_ids)
    task_ids.extend(chain_task_ids)
    if args.profile == "stress":
        _ensure_stress_extras(db, ctx, agent_id=agents[0].id, run_ids=run_ids, thread_ids=thread_ids, task_ids=task_ids)

    summary = ScenarioSeedSummary(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id or "",
        profile=args.profile,
        agent_ids=[agent.id for agent in agents],
        thread_ids=thread_ids,
        knowledge_ids=[item.id for item in knowledge],
        workflow_ids=[item.id for item in workflows],
        run_ids=run_ids,
        task_ids=task_ids,
        provider_ids=provider_ids,
        model_refs=model_refs,
        plugin_refs=plugin_refs,
        secret_ids=secret_ids,
        citation_sources=citation_sources,
        agent_chain_refs=agent_chain_refs,
    )
    if args.json_output:
        output_path = Path(args.json_output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.model_dump(), indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> int:
    args = _parse_args()
    db = get_db_sync()
    try:
        summary = asyncio.run(seed_enterprise_mvp_scenarios(db, args))
        print(json.dumps(summary.model_dump(), indent=2, sort_keys=True))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
