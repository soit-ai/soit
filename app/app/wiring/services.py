"""wiring.services

Module-level service factories.

API layer should depend on these factories (or directly on application services),
instead of constructing infra repositories/installers itself.

This keeps composition rules clear:
- api -> wiring -> (modules.infra + adapters + kernel)
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.settings.settings import settings
from app.kernel.runtime.core.service import RuntimeCoreService
from app.kernel.responses.repository import ResponseEventRepository, ResponseRepository
from app.kernel.responses.orchestrator import ResponseOrchestrator, ResponseProjectionCoordinator
from app.kernel.responses.service import ResponseService

# Knowledge runtime backend backed by the internal knowledge storage layer
from app.modules.knowledge.infra.repository import (
    KnowledgeRepository,
    DocumentRepository,
    ChunkRepository,
    IndexRepository,
    IngestTaskRepository,
)
from app.modules.knowledge.runtime.pipeline import DocumentPipeline
from app.modules.knowledge.runtime.retrieval import RetrievalService
from app.modules.knowledge.runtime.embedding import EmbeddingService
from app.modules.knowledge.runtime.index_builder import IndexBuilder

# Identity
from app.modules.identity.application.service import IdentityService
from app.modules.identity.infra.repository import (
    UserRepository,
    TenantRepository,
    TenantMembershipRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
    ApiKeyRepository,
    ResourceGrantRepository,
)
from app.kernel.identity.auth import JWTManager

# Modelhub
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.infra.providers import ProviderCatalogAdapter
from app.modules.modelhub.infra.repository import (
    PlatformModelRepository,
    ProviderRepository,
    ProviderModelRepository,
    ProviderModelTombstoneRepository,
    SyncJobRepository,
)
from app.wiring.container import get_container

# Plugin
from app.modules.plugin.infra.repository import PluginRepository, PluginInstallationRepository
from app.modules.plugin.infra.installer import PluginInstaller
from app.modules.plugin.application.service import PluginService
from app.modules.skill.application.service import SkillService
from app.modules.integrations.mcp.application.service import MCPService
from app.modules.observability.application.service import ObservabilityService

# Workflow
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.infra.repository import (
    WorkflowPublishRepository,
    WorkflowRepository,
    WorkflowVersionRepository,
)
from app.modules.knowledge.application.service import KnowledgeService
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService

# Secrets
from app.modules.secrets.application.service import SecretsService
from app.modules.secrets.infra.repository import SecretRepository

# Agent
from app.modules.agent.application.application_service import AgentApplicationService

# Memory
from app.modules.memory.application.service import MemoryService
from app.modules.memory.infra.repository import MemoryRepository
# Notification
from app.modules.notification.application.service import NotificationService
from app.modules.notification.infra.repository import NotificationRepository
# Run (kernel trace)
from app.kernel.trace.service import RunService
# Security
from app.modules.security.application.service import SecurityService
# Kernel tracing
from app.kernel.trace.writer import TraceWriter


def _build_knowledge_runtime(*, db: Session, ctx: RequestContext) -> dict[str, object]:
    """Shared knowledge runtime dependencies backed by the internal knowledge storage layer."""

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    storage_port = container.get_storage_port(ctx=ctx, trace_writer=trace_writer)
    vector_port = container.get_vector_port(ctx=ctx, trace_writer=trace_writer)
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)

    embedding_service = EmbeddingService(llm_port)
    index_builder = IndexBuilder(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )
    pipeline = DocumentPipeline(
        db=db,
        ctx=ctx,
        storage_port=storage_port,
        trace_writer=trace_writer,
        embedding_service=embedding_service,
        index_builder=index_builder,
    )

    retrieval_service = RetrievalService(
        db=db,
        ctx=ctx,
        vector_port=vector_port,
        llm_port=llm_port,
        embedding_service=embedding_service,
        storage_port=storage_port,
    )

    knowledge_repo = KnowledgeRepository(db, ctx)
    document_repo = DocumentRepository(db, ctx)
    chunk_repo = ChunkRepository(db, ctx)
    index_repo = IndexRepository(db, ctx)
    ingest_task_repo = IngestTaskRepository(db, ctx)

    return {
        "db": db,
        "ctx": ctx,
        "knowledge_repo": knowledge_repo,
        "document_repo": document_repo,
        "chunk_repo": chunk_repo,
        "index_repo": index_repo,
        "ingest_task_repo": ingest_task_repo,
        "pipeline": pipeline,
        "retrieval_service": retrieval_service,
        "index_builder": index_builder,
        "storage_port": storage_port,
        "vector_port": vector_port,
        "trace_writer": trace_writer,
    }


def build_knowledge_service(*, db: Session, ctx: RequestContext) -> KnowledgeService:
    """Knowledge service factory."""

    return KnowledgeService(runtime_service=build_knowledge_runtime_service(db=db, ctx=ctx))


def build_knowledge_runtime_service(*, db: Session, ctx: RequestContext) -> KnowledgeRuntimeService:
    """Internal knowledge storage/runtime factory."""

    return KnowledgeRuntimeService(**_build_knowledge_runtime(db=db, ctx=ctx))


def build_identity_service(*, db: Session) -> IdentityService:
    """IdentityService factory.

    Note: workspace repositories are scoped to RequestContext because they are tenant-aware.
    """
    jwt_manager = JWTManager(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
    )

    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    tenant_membership_repo = TenantMembershipRepository(db)
    api_key_repo = ApiKeyRepository(db)

    workspace_repo_factory: Callable[[RequestContext], WorkspaceRepository] = lambda ctx: WorkspaceRepository(db, ctx)
    workspace_membership_repo_factory: Callable[[RequestContext], WorkspaceMembershipRepository] = (
        lambda ctx: WorkspaceMembershipRepository(db, ctx)
    )
    resource_grant_repo_factory: Callable[[RequestContext], ResourceGrantRepository] = (
        lambda ctx: ResourceGrantRepository(db, ctx)
    )

    return IdentityService(
        db=db,
        jwt_manager=jwt_manager,
        user_repo=user_repo,
        tenant_repo=tenant_repo,
        tenant_membership_repo=tenant_membership_repo,
        workspace_repo_factory=workspace_repo_factory,
        workspace_membership_repo_factory=workspace_membership_repo_factory,
        api_key_repo=api_key_repo,
        resource_grant_repo_factory=resource_grant_repo_factory,
    )


def build_modelhub_service(*, db: Session, ctx: RequestContext) -> ModelHubService:
    provider_repo = ProviderRepository(db, ctx)
    platform_model_repo = PlatformModelRepository(db, ctx)
    provider_model_repo = ProviderModelRepository(db, ctx)
    tombstone_repo = ProviderModelTombstoneRepository(db, ctx)
    sync_job_repo = SyncJobRepository(db, ctx)
    container = get_container()
    secrets_port = container.get_secrets_port(ctx)
    catalog_adapter = ProviderCatalogAdapter()
    return ModelHubService(
        db,
        ctx,
        provider_repo,
        platform_model_repo,
        provider_model_repo,
        tombstone_repo,
        sync_job_repo,
        secrets_port,
        catalog_adapter,
    )


def _build_plugin_backend(*, db: Session, ctx: RequestContext) -> PluginService:
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)
    installer = PluginInstaller()
    return PluginService(db, ctx, plugin_repo, installation_repo, installer)


def build_plugin_service(*, db: Session, ctx: RequestContext) -> PluginService:
    """Plugin service factory."""

    return _build_plugin_backend(db=db, ctx=ctx)


def build_skill_service(*, db: Session, ctx: RequestContext) -> SkillService:
    """Skill service factory."""

    return SkillService(db=db, ctx=ctx)


def build_mcp_service(*, db: Session, ctx: RequestContext) -> MCPService:
    """MCP service factory."""

    return MCPService(db=db, ctx=ctx)


def build_observability_service(*, db: Session, ctx: RequestContext) -> ObservabilityService:
    """Observability service factory."""

    return ObservabilityService(db=db, ctx=ctx)


def build_workflow_service(*, db: Session, ctx: RequestContext) -> WorkflowService:
    container = get_container()
    workflow_repo = WorkflowRepository(db, ctx)
    version_repo = WorkflowVersionRepository(db, ctx)
    publish_repo = WorkflowPublishRepository(db, ctx)
    return WorkflowService(
        db=db,
        ctx=ctx,
        workflow_repo=workflow_repo,
        version_repo=version_repo,
        publish_repo=publish_repo,
        event_bus=container.get_event_bus(),
        response_service=build_response_service(db=db, ctx=ctx),
    )


def build_agent_service(*, db: Session, ctx: RequestContext) -> AgentApplicationService:
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    tool_port = container.get_tool_port(ctx=ctx)
    return AgentApplicationService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        memory_service=build_memory_service(db=db, ctx=ctx),
        trace_writer=trace_writer,
        response_service=build_response_service(db=db, ctx=ctx),
    )


def build_memory_service(*, db: Session, ctx: RequestContext) -> MemoryService:
    memory_repo = MemoryRepository(db, ctx)
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    vector_port = container.get_vector_port(ctx=ctx, trace_writer=trace_writer)
    return MemoryService(
        db=db,
        ctx=ctx,
        memory_repo=memory_repo,
        llm_port=llm_port,
        vector_port=vector_port,
        trace_writer=trace_writer,
    )


def build_notification_service(*, db: Session, ctx: RequestContext) -> NotificationService:
    """NotificationService factory."""
    notification_repo = NotificationRepository(db, ctx)
    return NotificationService(db=db, ctx=ctx, repo=notification_repo)


def build_run_service(*, db: Session, ctx: RequestContext) -> RunService:
    """RunService factory."""
    return RunService(db=db, ctx=ctx)


def build_security_service(*, db: Session, ctx: RequestContext) -> SecurityService:
    """SecurityService factory."""
    return SecurityService(db=db, ctx=ctx)


def build_secrets_service(*, db: Session, ctx: RequestContext) -> SecretsService:
    """SecretsService factory."""
    secret_repo = SecretRepository(db, ctx)
    container = get_container()
    secrets_port = container.get_secrets_port(ctx)
    return SecretsService(ctx=ctx, repo=secret_repo, secrets_port=secrets_port)


def build_response_service(*, db: Session, ctx: RequestContext) -> ResponseService:
    """Response resource/projection service factory."""

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    return ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )


def build_response_projection_coordinator(*, db: Session, ctx: RequestContext) -> ResponseProjectionCoordinator:
    """Response semantic projection coordinator factory."""

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    return ResponseProjectionCoordinator(
        response_service=response_service,
        llm_port=container.get_llm_port(ctx=ctx, trace_writer=trace_writer),
        runtime_core=RuntimeCoreService(db=db, ctx=ctx),
    )


def build_response_orchestrator(*, db: Session, ctx: RequestContext) -> ResponseOrchestrator:
    """Backward-compatible alias for the response projection coordinator factory."""

    return build_response_projection_coordinator(db=db, ctx=ctx)
