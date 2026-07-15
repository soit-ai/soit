"""repository

ModelHub repositories.
"""

from __future__ import annotations

import builtins

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.modelhub.domain.models import (
    PlatformModel,
    Provider,
    ProviderModel,
    SyncJob,
)


class PlatformModelRepository(Repository[PlatformModel]):
    """Repository for platform model catalog."""

    PLATFORM_TENANT_ID = "platform"
    PLATFORM_WORKSPACE_ID = "platform"

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(PlatformModel, db, ctx)

    def _apply_scope(self, query):
        """Disable tenant/workspace scoping for platform catalog."""
        return query

    def create(self, model: PlatformModel) -> PlatformModel:
        """Create a platform model with platform scope."""
        model.tenant_id = self.PLATFORM_TENANT_ID
        model.workspace_id = self.PLATFORM_WORKSPACE_ID
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def get_by_kind_and_model_id(self, provider_kind: str, model_id: str) -> PlatformModel | None:
        query = select(PlatformModel).where(
            and_(
                PlatformModel.provider_kind == provider_kind,
                PlatformModel.model_id == model_id,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_by_provider_kind(self, provider_kind: str, limit: int = 200) -> list[PlatformModel]:
        query = (
            select(PlatformModel)
            .where(PlatformModel.provider_kind == provider_kind)
            .order_by(desc(PlatformModel.updated_at))
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def list_active_by_provider_kind(self, provider_kind: str, limit: int = 500) -> list[PlatformModel]:
        query = (
            select(PlatformModel)
            .where(
                and_(
                    PlatformModel.provider_kind == provider_kind,
                    PlatformModel.status == "active",
                )
            )
            .order_by(desc(PlatformModel.updated_at))
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)


class ProviderRepository(Repository[Provider]):
    """Repository for providers."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(Provider, db, ctx)

    def get_by_name(self, name: str) -> Provider | None:
        query = select(Provider).where(
            and_(
                Provider.tenant_id == self.ctx.tenant_id,
                Provider.workspace_id == self.ctx.workspace_id,
                Provider.name == name,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_by_slug(self, slug: str) -> Provider | None:
        query = select(Provider).where(
            and_(
                Provider.tenant_id == self.ctx.tenant_id,
                Provider.workspace_id == self.ctx.workspace_id,
                Provider.slug == slug,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list(self, limit: int = 200) -> builtins.list[Provider]:
        query = (
            select(Provider)
            .where(
                and_(
                    Provider.tenant_id == self.ctx.tenant_id,
                    Provider.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(Provider.updated_at))
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)


class ProviderModelRepository(Repository[ProviderModel]):
    """Repository for provider models."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(ProviderModel, db, ctx)

    def list_by_provider(
        self,
        provider_id: str,
        limit: int = 200,
        *,
        status: str | None = None,
        include_removed: bool = False,
    ) -> list[ProviderModel]:
        clauses = [
            ProviderModel.tenant_id == self.ctx.tenant_id,
            ProviderModel.workspace_id == self.ctx.workspace_id,
            ProviderModel.provider_id == provider_id,
        ]
        if status:
            clauses.append(ProviderModel.status == status)
        elif not include_removed:
            clauses.append(ProviderModel.status != "removed")
        query = (
            select(ProviderModel)
            .where(and_(*clauses))
            .order_by(desc(ProviderModel.updated_at))
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def latest_synced_at_by_provider(self, provider_id: str):
        query = select(func.max(ProviderModel.last_synced_at)).where(
            and_(
                ProviderModel.tenant_id == self.ctx.tenant_id,
                ProviderModel.workspace_id == self.ctx.workspace_id,
                ProviderModel.provider_id == provider_id,
            )
        )
        result = self.db.exec(query).first()
        if isinstance(result, tuple):
            return result[0]
        if hasattr(result, "_mapping"):
            return result[0]
        return result

    def get_by_provider_and_model_id(self, provider_id: str, model_id: str) -> ProviderModel | None:
        query = select(ProviderModel).where(
            and_(
                ProviderModel.tenant_id == self.ctx.tenant_id,
                ProviderModel.workspace_id == self.ctx.workspace_id,
                ProviderModel.provider_id == provider_id,
                ProviderModel.model_id == model_id,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_by_provider_and_platform_model_id(
        self, provider_id: str, platform_model_id: str
    ) -> ProviderModel | None:
        query = select(ProviderModel).where(
            and_(
                ProviderModel.tenant_id == self.ctx.tenant_id,
                ProviderModel.workspace_id == self.ctx.workspace_id,
                ProviderModel.provider_id == provider_id,
                ProviderModel.platform_model_id == platform_model_id,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def get_by_provider_kind_and_model_id(
        self, provider_kind: str, model_id: str
    ) -> ProviderModel | None:
        query = select(ProviderModel).where(
            and_(
                ProviderModel.tenant_id == self.ctx.tenant_id,
                ProviderModel.workspace_id == self.ctx.workspace_id,
                ProviderModel.provider_kind == provider_kind,
                ProviderModel.model_id == model_id,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)


class SyncJobRepository(Repository[SyncJob]):
    """Repository for provider sync jobs."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(SyncJob, db, ctx)

    def list_by_provider(self, provider_id: str, limit: int = 50) -> list[SyncJob]:
        query = (
            select(SyncJob)
            .where(
                and_(
                    SyncJob.tenant_id == self.ctx.tenant_id,
                    SyncJob.workspace_id == self.ctx.workspace_id,
                    SyncJob.provider_id == provider_id,
                )
            )
            .order_by(desc(SyncJob.started_at))
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)
