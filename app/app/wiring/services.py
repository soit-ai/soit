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

# Chat
from app.modules.chat.application.service import ChatService
from app.modules.chat.application.config_provider import ChatConfigProvider
from app.modules.chat.infra.repository import ConversationRepository, MessageRepository

# Dataset
from app.modules.dataset.application.service import DatasetService
from app.modules.dataset.infra.repository import (
    DatasetRepository,
    DocumentRepository,
    ChunkRepository,
    IndexRepository,
    IngestTaskRepository,
)
from app.modules.dataset.runtime.pipeline import DocumentPipeline
from app.modules.dataset.runtime.retrieval import RetrievalService
from app.modules.dataset.runtime.embedding import EmbeddingService
from app.modules.dataset.runtime.index_builder import IndexBuilder

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

# AppCenter
from app.modules.appcenter.application.service import AppService
from app.modules.appcenter.infra.repository import (
    AppRepository,
    AppVersionRepository,
    AppMarketRepository,
    AppInstallationRepository,
)

# PluginMarket
from app.modules.pluginmarket.application.service import PluginMarketService
from app.modules.pluginmarket.infra.repository import PluginRepository, PluginInstallationRepository
from app.modules.pluginmarket.infra.installer import PluginInstaller

# Workflow
from app.modules.workflow.application.app_facade import WorkflowAppFacadeService

# Secrets
from app.modules.secrets.application.service import SecretsService
from app.modules.secrets.infra.repository import SecretRepository

# Bot
from app.modules.bot.application.app_facade import BotAppFacadeService
# Agent
from app.modules.agent.application.app_facade import AgentAppFacadeService

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
from app.wiring import get_container


def build_chat_service(*, db: Session, ctx: RequestContext) -> ChatService:
    conversation_repo = ConversationRepository(db, ctx)
    message_repo = MessageRepository(db, ctx)
    config_provider = ChatConfigProvider(db, ctx)
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    return ChatService(
        db,
        ctx,
        conversation_repo,
        message_repo,
        llm_port=llm_port,
        trace_writer=trace_writer,
        config_provider=config_provider,
        dataset_service_factory=lambda: build_dataset_service(db=db, ctx=ctx),
    )


def build_dataset_service(*, db: Session, ctx: RequestContext) -> DatasetService:
    """DatasetService with runtime pipeline + retrieval wired."""
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

    dataset_repo = DatasetRepository(db, ctx)
    document_repo = DocumentRepository(db, ctx)
    chunk_repo = ChunkRepository(db, ctx)
    index_repo = IndexRepository(db, ctx)
    ingest_task_repo = IngestTaskRepository(db, ctx)

    return DatasetService(
        db,
        ctx,
        dataset_repo,
        document_repo,
        chunk_repo,
        index_repo,
        ingest_task_repo,
        pipeline,
        retrieval_service,
        index_builder=index_builder,
        storage_port=storage_port,
        vector_port=vector_port,
        trace_writer=trace_writer,
    )


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


def build_pluginmarket_service(*, db: Session, ctx: RequestContext) -> PluginMarketService:
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)
    installer = PluginInstaller()
    return PluginMarketService(db, ctx, plugin_repo, installation_repo, installer)


def build_workflow_service(*, db: Session, ctx: RequestContext) -> WorkflowAppFacadeService:
    container = get_container()
    app_repo = AppRepository(db, ctx)
    version_repo = AppVersionRepository(db, ctx)
    return WorkflowAppFacadeService(
        db=db,
        ctx=ctx,
        app_repo=app_repo,
        version_repo=version_repo,
        event_bus=container.get_event_bus(),
    )


def build_bot_service(*, db: Session, ctx: RequestContext) -> BotAppFacadeService:
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    return BotAppFacadeService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        trace_writer=trace_writer,
        event_bus=container.get_event_bus(),
    )


def build_agent_app_service(*, db: Session, ctx: RequestContext) -> AgentAppFacadeService:
    return AgentAppFacadeService(
        db=db,
        ctx=ctx,
        event_bus=get_container().get_event_bus(),
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


def build_appcenter_service(*, db: Session, ctx: RequestContext) -> AppService:
    """AppService factory."""
    app_repo = AppRepository(db, ctx)
    version_repo = AppVersionRepository(db, ctx)
    market_repo = AppMarketRepository(db, ctx)
    installation_repo = AppInstallationRepository(db, ctx)
    return AppService(
        db=db,
        ctx=ctx,
        app_repo=app_repo,
        app_version_repo=version_repo,
        app_market_repo=market_repo,
        app_installation_repo=installation_repo,
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
