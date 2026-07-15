"""Plugin domain repository."""


import builtins

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginRelease,
    PluginVersion,
)


class PluginRepository(Repository[Plugin]):
    """Repository for Plugin model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize plugin repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Plugin, db, ctx)

    def get_by_name_version(self, name: str, version: str) -> Plugin | None:
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
        return self.db.exec(query).first()

    def list(
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

        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def get_by_name(self, name: str) -> Plugin | None:
        query = select(Plugin).where(
            and_(
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
                Plugin.name == name,
            )
        )
        return self._unwrap_result(self.db.exec(query).first())


class PluginInstallationRepository(Repository[PluginInstallation]):
    """Repository for PluginInstallation model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize plugin installation repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(PluginInstallation, db, ctx)

    def create(self, installation: PluginInstallation) -> PluginInstallation:
        """Create a new installation.

        Args:
            installation: PluginInstallation instance.

        Returns:
            Created PluginInstallation instance.
        """
        self.db.add(installation)
        self.db.commit()
        self.db.refresh(installation)
        return installation

    def get_by_plugin(self, plugin_id: str) -> PluginInstallation | None:
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
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_by_workspace(
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

        return self._unwrap_all(list(self.db.exec(query).all()))

    def list_by_plugin(self, plugin_id: str) -> list[PluginInstallation]:
        query = select(PluginInstallation).where(
            and_(
                PluginInstallation.tenant_id == self.ctx.tenant_id,
                PluginInstallation.workspace_id == self.ctx.workspace_id,
                PluginInstallation.plugin_id == plugin_id,
            )
        ).order_by(desc(PluginInstallation.created_at))
        return self._unwrap_all(list(self.db.exec(query).all()))


class PluginVersionRepository(Repository[PluginVersion]):
    """Repository for plugin versions."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(PluginVersion, db, ctx)

    def next_version_number(self, plugin_id: str) -> int:
        versions = self.list_by_plugin(plugin_id, limit=1_000, offset=0)
        return (max([item.version for item in versions], default=0) + 1)

    def list_by_plugin(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> list[PluginVersion]:
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
        return self._unwrap_all(list(self.db.exec(query).all()))


class PluginReleaseRepository(Repository[PluginRelease]):
    """Repository for plugin release ledger entries."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(PluginRelease, db, ctx)

    def list_by_plugin(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> list[PluginRelease]:
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
        return self._unwrap_all(list(self.db.exec(query).all()))


class PluginInstalledArtifactRepository(Repository[PluginInstalledArtifact]):
    """Repository for plugin-projected artifacts."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(PluginInstalledArtifact, db, ctx)

    def get_by_ref(self, *, plugin_id: str, artifact_ref: str) -> PluginInstalledArtifact | None:
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == self.ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == self.ctx.workspace_id,
                PluginInstalledArtifact.plugin_id == plugin_id,
                PluginInstalledArtifact.artifact_ref == artifact_ref,
            )
        )
        return self._unwrap_result(self.db.exec(query).first())

    def list(
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
        return self._unwrap_all(list(self.db.exec(query).all()))

    def list_by_installation(self, installation_id: str) -> builtins.list[PluginInstalledArtifact]:
        query = select(PluginInstalledArtifact).where(
            and_(
                PluginInstalledArtifact.tenant_id == self.ctx.tenant_id,
                PluginInstalledArtifact.workspace_id == self.ctx.workspace_id,
                PluginInstalledArtifact.installation_id == installation_id,
            )
        )
        return self._unwrap_all(list(self.db.exec(query).all()))
