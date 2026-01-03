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
from app.modules.chat.infra.repository import ConversationRepository, MessageRepository

# Dataset
from app.modules.dataset.application.service import DatasetService
from app.modules.dataset.infra.repository import DatasetRepository, DocumentRepository, ChunkRepository, IndexRepository
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
)
from app.kernel.identity.auth import JWTManager

# Modelhub
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.infra.repository import ModelRepository

# PluginMarket
from app.modules.pluginmarket.application.service import PluginMarketService
from app.modules.pluginmarket.infra.repository import PluginRepository, PluginInstallationRepository
from app.modules.pluginmarket.infra.installer import PluginInstaller

# Workflow
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.infra.repository import WorkflowRepository, WorkflowVersionRepository

# Kernel tracing
from app.kernel.trace.writer import TraceWriter
from app.wiring import get_container


def build_chat_service(*, db: Session, ctx: RequestContext) -> ChatService:
    conversation_repo = ConversationRepository(db, ctx)
    message_repo = MessageRepository(db, ctx)
    return ChatService(db, ctx, conversation_repo, message_repo)


def build_dataset_service(*, db: Session, ctx: RequestContext) -> DatasetService:
    """DatasetService with runtime pipeline + retrieval wired."""
    trace_writer = TraceWriter(db, ctx)

    container = get_container()
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

    return DatasetService(
        db,
        ctx,
        dataset_repo,
        document_repo,
        chunk_repo,
        index_repo,
        pipeline,
        retrieval_service,
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

    workspace_repo_factory: Callable[[RequestContext], WorkspaceRepository] = lambda ctx: WorkspaceRepository(db, ctx)
    workspace_membership_repo_factory: Callable[[RequestContext], WorkspaceMembershipRepository] = (
        lambda ctx: WorkspaceMembershipRepository(db, ctx)
    )

    return IdentityService(
        db=db,
        jwt_manager=jwt_manager,
        user_repo=user_repo,
        tenant_repo=tenant_repo,
        tenant_membership_repo=tenant_membership_repo,
        workspace_repo_factory=workspace_repo_factory,
        workspace_membership_repo_factory=workspace_membership_repo_factory,
    )


def build_modelhub_service(*, db: Session, ctx: RequestContext) -> ModelHubService:
    model_repo = ModelRepository(db, ctx)
    return ModelHubService(db, ctx, model_repo)


def build_pluginmarket_service(*, db: Session, ctx: RequestContext) -> PluginMarketService:
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)
    installer = PluginInstaller()
    return PluginMarketService(db, ctx, plugin_repo, installation_repo, installer)


def build_workflow_service(*, db: Session, ctx: RequestContext) -> WorkflowService:
    workflow_repo = WorkflowRepository(db, ctx)
    version_repo = WorkflowVersionRepository(db, ctx)
    return WorkflowService(db, ctx, workflow_repo, version_repo)
