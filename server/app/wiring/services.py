"""wiring.services

Module-level service factories.

API layer should depend on these factories (or directly on application services),
instead of constructing infra repositories/installers itself.

This keeps composition rules clear:
- api -> wiring -> (modules.infra + adapters + kernel)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.auth import JWTManager
from app.kernel.runtime.attachments.service import AttachmentService
from app.kernel.runtime.responses.orchestrator import ResponseProjectionCoordinator
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService

# Run (kernel trace)
from app.kernel.runtime.runs.service import RunService

# Kernel tracing
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.threads.service import ThreadService

# Agent
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.evaluation.application.judge import LLMRegressionJudge
from app.modules.evaluation.application.service import RegressionEvaluationService

# Identity
from app.modules.identity.application.service import IdentityService
from app.modules.identity.infra.repository import (
    ApiKeyRepository,
    PinnedObjectRepository,
    ResourceGrantRepository,
    SavedViewRepository,
    TenantMembershipRepository,
    TenantRepository,
    UserMfaRepository,
    UserRepository,
    UserSessionRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.modules.knowledge.application.service import KnowledgeService

# Knowledge runtime backend backed by the internal knowledge storage layer
from app.modules.knowledge.infra.repository import (
    ChunkRepository,
    DocumentRepository,
    IndexRepository,
    IngestTaskRepository,
    KnowledgeRepository,
)
from app.modules.knowledge.runtime.embedding import EmbeddingService
from app.modules.knowledge.runtime.index_builder import IndexBuilder
from app.modules.knowledge.runtime.pipeline import DocumentPipeline
from app.modules.knowledge.runtime.retrieval import RetrievalService

# Memory
from app.modules.memory.application.service import MemoryService
from app.modules.memory.infra.repository import MemoryRepository

# Modelhub
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.infra.providers import ProviderCatalogAdapter
from app.modules.modelhub.infra.repository import (
    PlatformModelRepository,
    ProviderModelRepository,
    ProviderRepository,
    SyncJobRepository,
)

# Notification
from app.modules.notification.application.service import NotificationService
from app.modules.notification.infra.repository import NotificationRepository
from app.modules.observe.application.service import ObserveService
from app.modules.plugin.application.service import PluginService
from app.modules.plugin.infra.installer import PluginInstaller

# Plugin
from app.modules.plugin.infra.repository import (
    PluginInstallationRepository,
    PluginInstalledArtifactRepository,
    PluginReleaseRepository,
    PluginRepository,
    PluginVersionRepository,
)

# Secrets
from app.modules.secrets.application.service import SecretsService
from app.modules.secrets.infra.repository import SecretRepository

# Security
from app.modules.security.application.service import SecurityService

# Workflow
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.infra.repository import (
    WorkflowPublishRepository,
    WorkflowRepository,
    WorkflowVersionRepository,
)
from app.settings.settings import settings
from app.wiring.container import get_container
from app.wiring.workflow_resources import KnowledgeRuntimeWorkflowQueryAdapter


def _get_optional_approval_checkpoint_gateway() -> Any | None:
    container = get_container()
    try:
        return container.get("approval_checkpoint_gateway")
    except ValueError:
        return None


def _build_knowledge_runtime(*, db: Session, ctx: RequestContext) -> dict[str, object]:
    """Shared knowledge runtime dependencies backed by the internal knowledge storage layer."""

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    storage_port = container.get_storage_port(ctx=ctx, trace_writer=trace_writer)
    vector_port = container.get_vector_port(ctx=ctx, trace_writer=trace_writer)
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    http_fetch_port = container.get_http_fetch_port()

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
        "http_fetch_port": http_fetch_port,
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
    session_repo = UserSessionRepository(db)
    mfa_repo = UserMfaRepository(db)

    def workspace_repo_factory(ctx: RequestContext) -> WorkspaceRepository:
        return WorkspaceRepository(db, ctx)

    def workspace_membership_repo_factory(ctx: RequestContext) -> WorkspaceMembershipRepository:
        return WorkspaceMembershipRepository(db, ctx)

    def resource_grant_repo_factory(ctx: RequestContext) -> ResourceGrantRepository:
        return ResourceGrantRepository(db, ctx)

    def saved_view_repo_factory(ctx: RequestContext) -> SavedViewRepository:
        return SavedViewRepository(db, ctx)

    def pin_repo_factory(ctx: RequestContext) -> PinnedObjectRepository:
        return PinnedObjectRepository(db, ctx)

    return IdentityService(
        db=db,
        session_repo=session_repo,
        saved_view_repo_factory=saved_view_repo_factory,
        pin_repo_factory=pin_repo_factory,
        mfa_repo=mfa_repo,
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
    from app.adapters.llm.litellm import LiteLLMPort
    from app.adapters.modelhub.references import DatabaseModelReferenceUsage
    from app.kernel.ports.llm.runtime_config import (
        resolve_litellm_runtime_config,
    )
    from app.modules.modelhub.domain.models import Provider

    provider_repo = ProviderRepository(db, ctx)
    platform_model_repo = PlatformModelRepository(db, ctx)
    provider_model_repo = ProviderModelRepository(db, ctx)
    sync_job_repo = SyncJobRepository(db, ctx)
    container = get_container()
    secrets_port = container.get_secrets_port(ctx, db=db)
    provider_resolver = container.get("llm_provider_resolver")
    catalog_adapter = ProviderCatalogAdapter()

    def build_litellm_port(
        provider: Provider,
        credentials: dict[str, str],
    ) -> LiteLLMPort:
        connection = provider.connection_config_json or {}
        retry_policy = connection.get("retry_policy") or {}
        timeout_ms = connection.get("timeout_ms")
        runtime = resolve_litellm_runtime_config(
            provider_kind=provider.kind,
            runtime_config=provider.runtime_config_json,
            connection_config=connection,
            auth_config=provider.auth_config_json,
            credential_secret_id=provider.credential_secret_id,
        )
        extra_credentials = {
            key: value for key, value in credentials.items() if key != "api_key"
        }
        return LiteLLMPort(
            provider_kind=provider.kind,
            litellm_provider=runtime.provider,
            litellm_params={**runtime.params, **extra_credentials},
            api_key=credentials.get("api_key"),
            api_base=provider.base_url,
            timeout=float(timeout_ms) / 1000 if timeout_ms is not None else 60.0,
            max_retries=int(retry_policy.get("max_retries", 3)),
        )

    return ModelHubService(
        db,
        ctx,
        provider_repo,
        platform_model_repo,
        provider_model_repo,
        sync_job_repo,
        secrets_port,
        catalog_adapter,
        litellm_port_factory=build_litellm_port,
        provider_cache_invalidator=provider_resolver.invalidate,
        runtime_llm_port=container.get_llm_port(ctx),
        model_reference_usage=DatabaseModelReferenceUsage(db, ctx),
    )


def _build_plugin_backend(*, db: Session, ctx: RequestContext) -> PluginService:
    from app.modules.workflow.infra.usage_query import (
        DatabasePublishedWorkflowUsagePort,
    )

    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)
    version_repo = PluginVersionRepository(db, ctx)
    release_repo = PluginReleaseRepository(db, ctx)
    artifact_repo = PluginInstalledArtifactRepository(db, ctx)
    installer = PluginInstaller()
    return PluginService(
        db,
        ctx,
        plugin_repo,
        installation_repo,
        installer,
        version_repo,
        release_repo,
        artifact_repo,
        DatabasePublishedWorkflowUsagePort(db, ctx),
        approval_checkpoint_gateway=_get_optional_approval_checkpoint_gateway(),
    )


def build_plugin_service(*, db: Session, ctx: RequestContext) -> PluginService:
    """Plugin service factory."""

    return _build_plugin_backend(db=db, ctx=ctx)


def build_observe_service(*, db: Session, ctx: RequestContext) -> ObserveService:
    """Observe service factory."""

    return ObserveService(db=db, ctx=ctx)


def build_evaluation_service(*, db: Session, ctx: RequestContext) -> RegressionEvaluationService:
    """Regression evaluation service factory."""

    judge = None
    if settings.evaluation_judge_model_ref:
        container = get_container()
        judge = LLMRegressionJudge(
            llm_port=container.get_llm_port(ctx=ctx),
            default_model=settings.evaluation_judge_model_ref,
        )
    return RegressionEvaluationService(db=db, ctx=ctx, judge=judge)


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
        approval_checkpoint_gateway=_get_optional_approval_checkpoint_gateway(),
        workflow_knowledge_query_port=KnowledgeRuntimeWorkflowQueryAdapter(
            runtime_service=build_knowledge_runtime_service(db=db, ctx=ctx),
            ctx=ctx,
        ),
    )


def build_agent_service(*, db: Session, ctx: RequestContext) -> AgentApplicationService:
    from app.adapters.plugins.skill_runtime import DatabaseSkillRuntimePort
    from app.kernel.ports.plugins.policy import PluginRuntimePolicyGateway
    from app.modules.agent.infra.capability_catalog import SqlAgentCapabilityCatalog

    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    tool_port = container.get_tool_port(ctx=ctx, trace_writer=trace_writer)
    skill_runtime_port = PluginRuntimePolicyGateway(
        gateway=DatabaseSkillRuntimePort(db),
        ctx=ctx,
    )
    return AgentApplicationService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        memory_service=build_memory_service(db=db, ctx=ctx),
        trace_writer=trace_writer,
        response_service=build_response_service(db=db, ctx=ctx),
        attachment_service=AttachmentService(
            db=db,
            ctx=ctx,
            storage_port=container.get_storage_port(ctx=ctx),
        ),
        approval_checkpoint_gateway=_get_optional_approval_checkpoint_gateway(),
        regression_evaluator=build_evaluation_service(db=db, ctx=ctx),
        plugin_runtime_port=skill_runtime_port,
        capability_catalog=SqlAgentCapabilityCatalog(db, ctx),
        workflow_knowledge_query_port=KnowledgeRuntimeWorkflowQueryAdapter(
            runtime_service=build_knowledge_runtime_service(db=db, ctx=ctx),
            ctx=ctx,
        ),
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
    return NotificationService(
        db=db,
        ctx=ctx,
        repo=notification_repo,
        secrets_service=build_secrets_service(db=db, ctx=ctx),
    )


def build_run_service(*, db: Session, ctx: RequestContext) -> RunService:
    """RunService factory."""
    return RunService(db=db, ctx=ctx)


def build_security_service(*, db: Session, ctx: RequestContext) -> SecurityService:
    """SecurityService factory."""
    from app.modules.identity.infra.policy_scope import DatabaseIdentityPolicyScopePort

    return SecurityService(
        db=db,
        ctx=ctx,
        identity_policy_scope=DatabaseIdentityPolicyScopePort(db, ctx),
    )


def build_secrets_service(*, db: Session, ctx: RequestContext) -> SecretsService:
    """SecretsService factory."""
    secret_repo = SecretRepository(db, ctx)
    container = get_container()
    value_store = container.get_secret_value_store()
    return SecretsService(ctx=ctx, repo=secret_repo, value_store=value_store)


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
        thread_service=ThreadService(db=db, ctx=ctx),
        storage_port=container.get_storage_port(ctx=ctx, trace_writer=trace_writer),
    )


