"""Bootstrap deterministic Enterprise MVP demo data."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import and_, select

from app.adapters.tools.router import RegistryToolRouterPort
from app.infra.db.session import get_db_sync
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatResponse,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
)
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import AgentCreate, AgentVersionCreate
from app.modules.agent.domain.models import Agent, AgentVersion
from app.modules.identity.application.schemas import UserCreate
from app.modules.identity.application.service import pwd_context
from app.modules.identity.domain.models import (
    Tenant,
    TenantMembership,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeIngestTask,
)
from app.modules.modelhub.domain.models import Provider, ProviderModel
from app.modules.workflow.application.schemas import WorkflowVersionCreate
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.domain.models import Workflow, WorkflowVersion
from app.modules.workflow.templates.ticket_triage import build_ticket_triage_template
from app.wiring.container import reset_container
from app.wiring.services import build_identity_service

DEMO_AGENT_NAME = "enterprise-mvp-agent"
DEMO_WORKFLOW_NAME = "Enterprise ticket triage"
DEMO_KNOWLEDGE_NAME = "enterprise_support_kb"
DEMO_DOC_KEY = "refund-policy.md"
DEMO_TICKET_TOOL_REF = "builtin.ticket.create_review_ticket"


class BootstrapLLMPort(LLMPort):
    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return ChatResponse(text="Enterprise MVP bootstrap stub response.", model=model)

    async def embed(self, texts, model, **kwargs):
        return EmbeddingResponse(embeddings=[[0.0, 0.0, 0.0] for _ in texts], tokens_used=len(texts), model=model)

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        return RerankResponse(
            results=[{"index": index, "document": document, "score": 1.0} for index, document in enumerate(documents[: top_n or None])],
            tokens_used=0,
            model=model,
        )


@dataclass
class BootstrapResult:
    tenant_id: str
    workspace_id: str
    user_id: str
    provider_id: str
    model_refs: list[str]
    knowledge_id: str
    document_id: str
    workflow_id: str
    workflow_version_id: str
    ticket_tool_ref: str
    agent_id: str
    agent_version_id: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Enterprise MVP demo data.")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="changeme123")
    parser.add_argument("--name", default="Admin")
    parser.add_argument("--tenant-name", default="default")
    parser.add_argument("--workspace-name", default="default")
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


def _scoped_demo_id(db, model: type[Any], legacy_id: str, ctx: RequestContext, stable_key: str) -> str:
    existing = _one(db, select(model).where(model.id == legacy_id))
    if existing is None or (
        getattr(existing, "tenant_id", None) == ctx.tenant_id
        and getattr(existing, "workspace_id", None) == ctx.workspace_id
    ):
        return legacy_id

    digest = hashlib.sha1(f"{ctx.tenant_id}:{ctx.workspace_id}:{stable_key}".encode()).hexdigest()[:12]
    return f"{legacy_id}_{digest}"


def _ensure_context(db, args: argparse.Namespace) -> RequestContext:
    identity = build_identity_service(db=db)
    user = identity.user_repo.get_by_email(args.email)
    if not user:
        tenant = identity.tenant_repo.get_by_name(args.tenant_name)
        if tenant is None:
            user, tenant, _, workspace_id = identity.register_user(
                UserCreate(email=args.email, password=args.password, name=args.name),
                tenant_name=args.tenant_name,
            )
            return RequestContext(
                tenant_id=tenant.id,
                workspace_id=workspace_id,
                user_id=user.id,
                tenant_role="Owner",
                workspace_role="Owner",
            )
        user = identity.user_repo.create(
            User(
                email=args.email,
                password_hash=pwd_context.hash(args.password),
                name=args.name,
            )
        )

    tenant = identity.tenant_repo.get_by_name(args.tenant_name)
    if tenant is None:
        membership = _one(db, select(TenantMembership).where(TenantMembership.user_id == user.id))
        tenant = identity.tenant_repo.get_by_id(membership.tenant_id) if membership else None
    if tenant is None:
        tenant = identity.tenant_repo.create(Tenant(name=args.tenant_name))

    tenant_membership = _one(
        db,
        select(TenantMembership).where(
            and_(TenantMembership.tenant_id == tenant.id, TenantMembership.user_id == user.id)
        ),
    )
    if tenant_membership is None:
        identity.tenant_membership_repo.create(TenantMembership(tenant_id=tenant.id, user_id=user.id, role="Owner"))

    workspace = _one(
        db,
        select(Workspace).where(and_(Workspace.tenant_id == tenant.id, Workspace.name == args.workspace_name)),
    )
    if workspace is None:
        workspace = Workspace(
            tenant_id=tenant.id,
            name=args.workspace_name,
            description="Enterprise MVP demo workspace",
            metadata_json={"demo": "enterprise_mvp"},
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

    workspace_membership = _one(
        db,
        select(WorkspaceMembership).where(
            and_(
                WorkspaceMembership.tenant_id == tenant.id,
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == user.id,
            )
        ),
    )
    if workspace_membership is None:
        db.add(
            WorkspaceMembership(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                user_id=user.id,
                role="Owner",
            )
        )
        db.commit()

    return RequestContext(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        tenant_role="Owner",
        workspace_role="Owner",
    )


def _ensure_provider_models(db, ctx: RequestContext) -> tuple[Provider, list[str]]:
    provider = _one(
        db,
        select(Provider).where(
            and_(
                Provider.tenant_id == ctx.tenant_id,
                Provider.workspace_id == ctx.workspace_id,
                Provider.name == "Enterprise MVP Stub",
            )
        ),
    )
    if provider is None:
        provider = Provider(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            kind="test",
            slug="enterprise-mvp-stub",
            name="Enterprise MVP Stub",
            base_url="stub://enterprise-mvp",
            status="active",
            sync_policy_json={"auto_sync": False},
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)
    elif not provider.slug:
        provider.slug = "enterprise-mvp-stub"
        db.add(provider)
        db.commit()
        db.refresh(provider)

    model_specs = [
        ("agent", "Enterprise MVP Agent", {"chat": True, "tool_calls": True}),
        ("workflow", "Enterprise MVP Workflow", {"chat": True}),
        ("embedding", "Enterprise MVP Embedding", {"embeddings": True, "dimension": 3}),
    ]
    model_refs: list[str] = []
    for model_id, display_name, capabilities in model_specs:
        model = _one(
            db,
            select(ProviderModel).where(
                and_(
                    ProviderModel.tenant_id == ctx.tenant_id,
                    ProviderModel.workspace_id == ctx.workspace_id,
                    ProviderModel.provider_id == provider.id,
                    ProviderModel.model_id == model_id,
                )
            ),
        )
        if model is None:
            model = ProviderModel(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                provider_id=provider.id,
                provider_kind=provider.kind,
                model_id=model_id,
                display_name=display_name,
                capabilities_json=capabilities,
                config_json={"bootstrap": "enterprise_mvp"},
                status="active",
                source="local",
                sync_status="in_sync",
            )
            db.add(model)
        else:
            model.display_name = display_name
            model.capabilities_json = capabilities
            model.status = "active"
            model.updated_at = utc_now()
        model_refs.append(f"model:{provider.kind}:{model_id}")
    db.commit()
    return provider, model_refs


def _ensure_knowledge(db, ctx: RequestContext) -> tuple[Knowledge, KnowledgeDocument]:
    now = utc_now()
    text = "Refund escalations require account verification before a review ticket is created."
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    knowledge = _one(
        db,
        select(Knowledge).where(
            and_(
                Knowledge.tenant_id == ctx.tenant_id,
                Knowledge.workspace_id == ctx.workspace_id,
                Knowledge.name == DEMO_KNOWLEDGE_NAME,
                Knowledge.deleted_at.is_(None),
            )
        ),
    )
    if knowledge is None:
        knowledge = Knowledge(
            id=_scoped_demo_id(db, Knowledge, "knw_enterprise_mvp", ctx, "knowledge"),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            name=DEMO_KNOWLEDGE_NAME,
            type="document",
            description="Enterprise support refund and escalation policy",
            visibility="workspace",
            default_embedding_model_ref="model:test:embedding",
            doc_count=1,
            chunk_count=1,
            last_ingested_at=now,
            last_indexed_at=now,
            tags=["enterprise", "mvp"],
            created_by=ctx.user_id,
            updated_by=ctx.user_id,
        )
        db.add(knowledge)
    else:
        knowledge.description = "Enterprise support refund and escalation policy"
        knowledge.visibility = "workspace"
        knowledge.default_embedding_model_ref = "model:test:embedding"
        knowledge.doc_count = 1
        knowledge.chunk_count = 1
        knowledge.last_ingested_at = now
        knowledge.last_indexed_at = now
        knowledge.tags = ["enterprise", "mvp"]
        knowledge.updated_by = ctx.user_id
        knowledge.updated_at = now
    db.commit()
    db.refresh(knowledge)

    index = _one(
        db,
        select(KnowledgeIndex).where(
            and_(
                KnowledgeIndex.tenant_id == ctx.tenant_id,
                KnowledgeIndex.workspace_id == ctx.workspace_id,
                KnowledgeIndex.knowledge_id == knowledge.id,
                KnowledgeIndex.name == "enterprise-mvp-primary",
                KnowledgeIndex.deleted_at.is_(None),
            )
        ),
    )
    if index is None:
        index = KnowledgeIndex(
            id=_scoped_demo_id(db, KnowledgeIndex, "idx_enterprise_mvp", ctx, f"index:{knowledge.id}"),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            knowledge_id=knowledge.id,
            name="enterprise-mvp-primary",
            is_primary=True,
            provider="milvus",
            collection_name=f"kb_{knowledge.id}_enterprise_mvp",
            embedding_model_ref="model:test:embedding",
            dimension=3,
            metric_type="cosine",
            status="ready",
            doc_count=1,
            chunk_count=1,
            vector_count=1,
            last_build_at=now,
            created_by=ctx.user_id,
            updated_by=ctx.user_id,
        )
        db.add(index)
    else:
        index.is_primary = True
        index.status = "ready"
        index.doc_count = 1
        index.chunk_count = 1
        index.vector_count = 1
        index.last_build_at = now
        index.updated_by = ctx.user_id
        index.updated_at = now
    db.commit()
    db.refresh(index)
    knowledge.default_index_id = index.id
    db.add(knowledge)
    db.commit()

    document = _one(
        db,
        select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.tenant_id == ctx.tenant_id,
                KnowledgeDocument.workspace_id == ctx.workspace_id,
                KnowledgeDocument.knowledge_id == knowledge.id,
                KnowledgeDocument.doc_key == DEMO_DOC_KEY,
                KnowledgeDocument.is_latest.is_(True),
            )
        ),
    )
    if document is None:
        document = KnowledgeDocument(
            id=_scoped_demo_id(db, KnowledgeDocument, "doc_enterprise_refund_policy", ctx, f"document:{knowledge.id}"),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            knowledge_id=knowledge.id,
            doc_key=DEMO_DOC_KEY,
            version=1,
            is_latest=True,
            source_kind="manual",
            source_uri="kb://refund-policy.md",
            title="Refund Policy",
            mime_type="text/markdown",
            filename=DEMO_DOC_KEY,
            size_bytes=len(text.encode("utf-8")),
            checksum=content_hash,
            content_hash=content_hash,
            status="indexed",
            index_meta_json={"index_id": index.id, "collection_name": index.collection_name},
            created_by=ctx.user_id,
            updated_by=ctx.user_id,
        )
        db.add(document)
    else:
        document.title = "Refund Policy"
        document.source_kind = "manual"
        document.source_uri = "kb://refund-policy.md"
        document.mime_type = "text/markdown"
        document.filename = DEMO_DOC_KEY
        document.size_bytes = len(text.encode("utf-8"))
        document.checksum = content_hash
        document.content_hash = content_hash
        document.status = "indexed"
        document.index_meta_json = {"index_id": index.id, "collection_name": index.collection_name}
        document.updated_by = ctx.user_id
        document.updated_at = now
    db.commit()
    db.refresh(document)

    chunk = _one(
        db,
        select(KnowledgeChunk).where(
            and_(
                KnowledgeChunk.tenant_id == ctx.tenant_id,
                KnowledgeChunk.workspace_id == ctx.workspace_id,
                KnowledgeChunk.knowledge_id == knowledge.id,
                KnowledgeChunk.document_id == document.id,
                KnowledgeChunk.chunk_key == f"{DEMO_DOC_KEY}:1:0",
            )
        ),
    )
    if chunk is None:
        chunk = KnowledgeChunk(
            id=_scoped_demo_id(db, KnowledgeChunk, "chunk_enterprise_refund_policy_0", ctx, f"chunk:{document.id}:0"),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            knowledge_id=knowledge.id,
            document_id=document.id,
            document_version=document.version,
            chunk_no=0,
            chunk_key=f"{DEMO_DOC_KEY}:1:0",
            content_hash=content_hash,
            text_preview=text,
            start_offset=0,
            end_offset=len(text),
            section_path=["Support", "Refunds"],
            char_count=len(text),
            token_count=12,
            embedding_model_ref="model:test:embedding",
            vector_ref=f"{index.collection_name}:0",
            indexed_at=now,
            index_status="indexed",
        )
        db.add(chunk)
    else:
        chunk.text_preview = text
        chunk.content_hash = content_hash
        chunk.embedding_model_ref = "model:test:embedding"
        chunk.vector_ref = f"{index.collection_name}:0"
        chunk.indexed_at = now
        chunk.index_status = "indexed"
        chunk.updated_at = now
    db.commit()

    task = _one(
        db,
        select(KnowledgeIngestTask).where(
            and_(
                KnowledgeIngestTask.tenant_id == ctx.tenant_id,
                KnowledgeIngestTask.workspace_id == ctx.workspace_id,
                KnowledgeIngestTask.knowledge_id == knowledge.id,
                KnowledgeIngestTask.document_id == document.id,
            )
        ),
    )
    if task is None:
        task = KnowledgeIngestTask(
            id=_scoped_demo_id(db, KnowledgeIngestTask, "ingest_enterprise_refund_policy", ctx, f"ingest:{document.id}"),
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            knowledge_id=knowledge.id,
            document_id=document.id,
            status="succeeded",
            payload_json={"doc_key": DEMO_DOC_KEY, "source_kind": "manual"},
            max_retries=1,
            started_at=now,
            finished_at=now,
            created_by=ctx.user_id,
            updated_by=ctx.user_id,
        )
        db.add(task)
    else:
        task.status = "succeeded"
        task.finished_at = now
        task.updated_at = now
        task.updated_by = ctx.user_id
    db.commit()
    return knowledge, document


async def _ensure_workflow(db, ctx: RequestContext) -> Workflow:
    service = WorkflowService(db=db, ctx=ctx)
    spec_json = build_ticket_triage_template()
    spec_json["name"] = DEMO_WORKFLOW_NAME
    workflow = _one(
        db,
        select(Workflow).where(
            and_(
                Workflow.tenant_id == ctx.tenant_id,
                Workflow.workspace_id == ctx.workspace_id,
                Workflow.name == DEMO_WORKFLOW_NAME,
                Workflow.deleted_at.is_(None),
            )
        ),
    )
    if workflow is None:
        workflow = await service.create_ticket_triage_template(name=DEMO_WORKFLOW_NAME)
    else:
        workflow.description = "Ticket triage workflow template"
        workflow.summary = "Classifies a support request, creates a governed review ticket, and returns citations."
        workflow.category = "support"
        workflow.tags = ["template", "ticket-triage", "enterprise", "mvp"]
        workflow.metadata_json = {"template_key": "ticket_triage", "bootstrap": "enterprise_mvp"}
        workflow.updated_by = ctx.user_id
        workflow.updated_at = utc_now()
        db.add(workflow)
        db.commit()

    if not workflow.current_version_id:
        version = await service.create_version(
            workflow.id,
            WorkflowVersionCreate(graph_json=spec_json, created_by=ctx.user_id or ""),
        )
        workflow = service._get_workflow(workflow.id)
        workflow.current_version_id = version.id
        db.add(workflow)
        db.commit()
    else:
        current_version = _one(
            db,
            select(WorkflowVersion).where(
                and_(
                    WorkflowVersion.tenant_id == ctx.tenant_id,
                    WorkflowVersion.workspace_id == ctx.workspace_id,
                    WorkflowVersion.id == workflow.current_version_id,
                )
            ),
        )
        if current_version is None or current_version.spec_json != spec_json:
            version = await service.create_version(
                workflow.id,
                WorkflowVersionCreate(graph_json=spec_json, created_by=ctx.user_id or ""),
            )
            workflow = service._get_workflow(workflow.id)
            workflow.current_version_id = version.id
            db.add(workflow)
            db.commit()

    if workflow.current_version_id and workflow.published_version_id != workflow.current_version_id:
        workflow = await service.publish_version(workflow.id, workflow.current_version_id)
    return workflow


async def _ensure_agent(db, ctx: RequestContext, knowledge: Knowledge, workflow: Workflow) -> Agent:
    service = AgentApplicationService(
        db=db,
        ctx=ctx,
        llm_port=BootstrapLLMPort(),
        tool_port=RegistryToolRouterPort(),
    )
    agent = service.agent_repo.get_by_name(DEMO_AGENT_NAME)
    if agent is None:
        agent = await service.create_agent(
            AgentCreate(
                name=DEMO_AGENT_NAME,
                description="Enterprise MVP demo agent",
                visibility="workspace",
                tags=["enterprise", "mvp"],
            )
        )
    else:
        agent.description = "Enterprise MVP demo agent"
        agent.visibility = "workspace"
        agent.tags = ["enterprise", "mvp"]
        agent.updated_by = ctx.user_id
        agent.updated_at = utc_now()
        db.add(agent)
        db.commit()
        db.refresh(agent)

    version_input = AgentVersionCreate(
        system_prompt="Use enterprise knowledge and ticket workflows.",
        temperature=0.1,
        bindings={
            "model_ref": "model:test:agent",
            "knowledge_refs": [f"knowledge:{knowledge.id}"],
            "tool_refs": [DEMO_TICKET_TOOL_REF],
            "workflow_refs": [f"wf:{workflow.id}"],
        },
        verify=False,
    )
    target_spec = service._build_spec(version_input)
    live_version = _one(
        db,
        select(AgentVersion).where(
            and_(
                AgentVersion.tenant_id == ctx.tenant_id,
                AgentVersion.workspace_id == ctx.workspace_id,
                AgentVersion.id == agent.published_version_id,
            )
        ),
    )
    if live_version is None or live_version.spec_json != target_spec:
        version = await service.create_version(agent.id, version_input)
        agent = await service.publish_version(agent.id, version.id, notes="Enterprise MVP bootstrap")
    return agent


async def bootstrap_enterprise_mvp(db, args: argparse.Namespace) -> BootstrapResult:
    reset_container()
    ctx = _ensure_context(db, args)
    provider, model_refs = _ensure_provider_models(db, ctx)
    knowledge, document = _ensure_knowledge(db, ctx)
    workflow = await _ensure_workflow(db, ctx)
    agent = await _ensure_agent(db, ctx, knowledge, workflow)
    return BootstrapResult(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id or "",
        provider_id=provider.id,
        model_refs=model_refs,
        knowledge_id=knowledge.id,
        document_id=document.id,
        workflow_id=workflow.id,
        workflow_version_id=workflow.published_version_id or workflow.current_version_id or "",
        ticket_tool_ref=DEMO_TICKET_TOOL_REF,
        agent_id=agent.id,
        agent_version_id=agent.published_version_id or agent.current_version_id or "",
    )


def main() -> int:
    args = _parse_args()
    db = get_db_sync()
    try:
        result = asyncio.run(bootstrap_enterprise_mvp(db, args))
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
