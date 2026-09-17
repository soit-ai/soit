"""Plugin domain repository."""


import builtins

from sqlalchemy import and_, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.repository import AsyncRepository
from app.kernel.contracts.context import RequestContext
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginRelease,
    PluginVersion,
)


class PluginRepository(AsyncRepository[Plugin]):
    """Repository for Plugin model."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        """Initialize plugin repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Plugin, db, ctx)

    async def get_by_name_version(self, name: str, version: str) -> Plugin | None:
        """Get plugin by name and version.

        Args:
            name: Plugin name.
            version: Plugin version.

        Returns:
            Plugin instance or None if not found.
        """
        query = select(Plugin).where(
            and_(
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
                Plugin.name == name,
                Plugin.version == version,
            )
        )
        return (await self.db.exec(query)).scalars().first()

    async def list(
        self,
        published_only: bool = False,
        plugin_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Plugin]:
        """List plugins.

        Args:
            published_only: Only return published plugins.
            limit: Maximum number of plugins.
            offset: Offset for pagination.

        Returns:
            List of Plugin instances.
        """
        query = select(Plugin).where(
            and_(
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
            )
        )

        if published_only:
            query = query.where(Plugin.publish_status == "published")
        if plugin_type:
            query = query.where(Plugin.plugin_type == plugin_type)

        query = query.order_by(desc(Plugin.created_at)).offset(offset).limit(limit)

        results = list((await self.db.exec(query)).scalars().all())
        return self._unwrap_all(results)

    async def get_by_name(self, name: str) -> Plugin | None:
        query = select(Plugin).where(
            and_(
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
                Plugin.name == name,
            )
        )
        return self._unwrap_result((await self.db.exec(query)).scalars().first())


class PluginInstallationRepository(AsyncRepository[PluginInstallation]):
    """Repository for PluginInstallation model."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        """Initialize plugin installation repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(PluginInstallation, db, ctx)

    async def create(self, installation: PluginInstallation) -> PluginInstallation:
        """Create a new installation.

        Args:
            installation: PluginInstallation instance.

        Returns:
            Created PluginInstallation instance.
        """
        self.db.add(installation)
        await self.db.commit()
        await self.db.refresh(installation)
        return installation

    async def get_by_plugin(self, plugin_id: str) -> PluginInstallation | None:
        """Get installation by plugin ID.

        Args:
            plugin_id: Plugin ID.

        Returns:
            PluginInstallation instance or None if not found.
        """
        query = select(PluginInstallation).where(
            and_(
                PluginInstallation.tenant_id == self.ctx.tenant_id,
                PluginInstallation.workspace_id == self.ctx.workspace_id,
                PluginInstallation.plugin_id == plugin_id,
            )
        )
        result = (await self.db.exec(query)).scalars().first()
        return self._unwrap_result(result)

    async def list_by_workspace(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PluginInstallation]:
        """List installations in workspace.

        Args:
            limit: Maximum number of installations.
            offset: Offset for pagination.

        Returns:
            List of PluginInstallation instances.
        """
        query = select(PluginInstallation).where(
            and_(
                PluginInstallation.tenant_id == self.ctx.tenant_id,
                PluginInstallation.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(PluginInstallation.created_at)).offset(offset).limit(limit)

        return self._unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def list_by_plugin(self, plugin_id: str) -> list[PluginInstallation]:
        query = select(PluginInstallation).where(
            and_(
                PluginInstallation.tenant_id == self.ctx.tenant_id,
                PluginInstallation.workspace_id == self.ctx.workspace_id,
                PluginInstallation.plugin_id == plugin_id,
            )
        ).order_by(desc(PluginInstallation.created_at))
        return self._unwrap_all(list((await self.db.exec(query)).scalars().all()))


class PluginVersionRepository(AsyncRepository[PluginVersion]):
    """Repository for plugin versions."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        super().__init__(PluginVersion, db, ctx)

    async def next_version_number(self, plugin_id: str) -> int:
        versions = await self.list_by_plugin(plugin_id, limit=1_000, offset=0)
        return (max([item.version for item in versions], default=0) + 1)

    async def list_by_plugin(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> list[PluginVersion]:
        query = (
            select(PluginVersion)
            .where(
                and_(
                    PluginVersion.tenant_id == self.ctx.tenant_id,
                    PluginVersion.workspace_id == self.ctx.workspace_id,
                    PluginVersion.plugin_id == plugin_id,
                )
            )
            .order_by(desc(PluginVersion.created_at))
            .offset(offset)
            .limit(limit)
        )
        return self._unwrap_all(list((await self.db.exec(query)).scalars().all()))


class PluginReleaseRepository(AsyncRepository[PluginRelease]):
    """Repository for plugin release ledger entries."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        super().__init__(PluginRelease, db, ctx)

    async def list_by_plugin(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> list[PluginRelease]:
        query = (
            select(PluginRelease)
            .where(
                and_(
                    PluginRelease.tenant_id == self.ctx.tenant_id,
                    PluginRelease.workspace_id == self.ctx.workspace_id,
                    PluginRelease.plugin_id == plugin_id,
                )
            )
            .order_by(desc(PluginRelease.created_at))
            .offset(offset)
            .limit(limit)
        )
        return self._unwrap_all(list((await self.db.exec(query)).scalars().all()))


class PluginInstalledArtifactRepository(AsyncRepository[PluginInstalledArtifact]):
    """Repository for plugin-projected artifacts."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        super().__init__(PluginInstalledArtifact, db, ctx)

    async def get_by_ref(self, *, plugin_id: str, artifact_ref: str) -> PluginInstalledArtifact | None:
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == self.ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == self.ctx.workspace_id,
                PluginInstalledArtifact.plugin_id == plugin_id,
                PluginInstalledArtifact.artifact_ref == artifact_ref,
            )
        )
        return self._unwrap_result((await self.db.exec(query)).scalars().first())

    async def list(
        self,
        *,
        plugin_id: str | None = None,
        artifact_kind: str | None = None,
        enabled: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PluginInstalledArtifact]:
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == self.ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == self.ctx.workspace_id,
            )
        )
        if plugin_id:
            query = query.where(PluginInstalledArtifact.plugin_id == plugin_id)
        if artifact_kind:
            query = query.where(PluginInstalledArtifact.artifact_kind == artifact_kind)
        if enabled is not None:
            query = query.where(PluginInstalledArtifact.enabled == enabled)
        query = query.order_by(desc(PluginInstalledArtifact.created_at)).offset(offset).limit(limit)
        return self._unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def list_by_installation(self, installation_id: str) -> builtins.list[PluginInstalledArtifact]:
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == self.ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == self.ctx.workspace_id,
                PluginInstalledArtifact.installation_id == installation_id,
            )
        )
        return self._unwrap_all(list((await self.db.exec(query)).scalars().all()))
