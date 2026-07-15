"""Plugin artifact projectors.

Projectors translate plugin package artifacts into internal domain objects or
runtime registry entries. PluginService owns lifecycle orchestration; these
classes own artifact-specific projection details.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry
from app.kernel.specs.validator import SpecValidator
from app.modules.plugin.application.ports import PluginProjectionRepositoryPort
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginVersion,
)


@dataclass(frozen=True)
class ArtifactProjection:
    artifact_kind: str
    artifact_ref: str
    artifact_id: str | None
    artifact_version_id: str | None
    metadata_json: dict[str, Any]


class PluginProjectionContext:
    def __init__(
        self,
        *,
        db: Session,
        ctx: RequestContext,
        plugin: Plugin,
        version: PluginVersion | None,
        installation: PluginInstallation | None,
        install_dir: Path,
        spec: dict[str, Any],
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.plugin = plugin
        self.version = version
        self.installation = installation
        self.install_dir = install_dir
        self.spec = spec
        self.files_dir = install_dir / "files"


class BaseProjector:
    artifact_kind: str

    def __init__(self, validator: SpecValidator | None = None) -> None:
        self.validator = validator or SpecValidator()

    def load_artifact(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> dict[str, Any]:
        path = self._artifact_path(projection_ctx, artifact_ref)
        if not path.exists():
            raise ValidationError(f"Plugin artifact file not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValidationError(f"Invalid plugin artifact JSON: {artifact_ref}: {exc}")
        if not isinstance(data, dict):
            raise ValidationError(f"Plugin artifact must be a JSON object: {artifact_ref}")
        return data

    def _artifact_path(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> Path:
        artifact_paths = (projection_ctx.spec.get("artifacts") or {}).get(self.artifact_kind_plural) or {}
        if isinstance(artifact_paths, dict) and artifact_ref in artifact_paths:
            return projection_ctx.files_dir / artifact_paths[artifact_ref]
        artifact_name = artifact_ref.split(":")[-1]
        return projection_ctx.files_dir / self.default_dir / f"{artifact_name}.json"

    @property
    def artifact_kind_plural(self) -> str:
        return f"{self.artifact_kind}s"

    @property
    def default_dir(self) -> str:
        return self.artifact_kind_plural

    async def apply_install(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> ArtifactProjection:
        raise NotImplementedError

    async def apply_enable(
        self,
        projection_ctx: PluginProjectionContext,
        artifact: PluginInstalledArtifact,
        enabled: bool,
    ) -> None:
        artifact.enabled = enabled
        artifact.state = "enabled" if enabled else "disabled"

    async def apply_uninstall(
        self,
        projection_ctx: PluginProjectionContext,
        artifact: PluginInstalledArtifact,
    ) -> None:
        artifact.enabled = False
        artifact.state = "archived"


class SkillProjector(BaseProjector):
    artifact_kind = "skill"
    default_dir = "skills"

    async def apply_install(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> ArtifactProjection:
        artifact = self.load_artifact(projection_ctx, artifact_ref)
        return ArtifactProjection(
            artifact_kind="skill",
            artifact_ref=artifact_ref,
            artifact_id=artifact_ref,
            artifact_version_id=None,
            metadata_json={"skill": artifact, "plugin": self._plugin_metadata(projection_ctx, artifact_ref)},
        )

    async def apply_enable(
        self,
        projection_ctx: PluginProjectionContext,
        artifact: PluginInstalledArtifact,
        enabled: bool,
    ) -> None:
        await super().apply_enable(projection_ctx, artifact, enabled)

    async def apply_uninstall(
        self,
        projection_ctx: PluginProjectionContext,
        artifact: PluginInstalledArtifact,
    ) -> None:
        await super().apply_uninstall(projection_ctx, artifact)

    def _plugin_metadata(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> dict[str, Any]:
        return {
            "id": projection_ctx.plugin.id,
            "name": projection_ctx.plugin.name,
            "version": projection_ctx.plugin.version,
            "plugin_version_id": projection_ctx.version.id if projection_ctx.version else None,
            "installation_id": projection_ctx.installation.id if projection_ctx.installation else None,
            "artifact_ref": artifact_ref,
        }


class MCPServerProjector(BaseProjector):
    artifact_kind = "mcp_server"
    artifact_kind_plural = "mcp_servers"
    default_dir = "mcp"

    async def apply_install(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> ArtifactProjection:
        artifact = self.load_artifact(projection_ctx, artifact_ref)
        return ArtifactProjection(
            artifact_kind="mcp_server",
            artifact_ref=artifact_ref,
            artifact_id=artifact_ref,
            artifact_version_id=None,
            metadata_json={"mcp_server": artifact, "plugin": self._plugin_metadata(projection_ctx, artifact_ref)},
        )

    async def apply_enable(
        self,
        projection_ctx: PluginProjectionContext,
        artifact: PluginInstalledArtifact,
        enabled: bool,
    ) -> None:
        await super().apply_enable(projection_ctx, artifact, enabled)

    async def apply_uninstall(
        self,
        projection_ctx: PluginProjectionContext,
        artifact: PluginInstalledArtifact,
    ) -> None:
        await super().apply_uninstall(projection_ctx, artifact)

    def _plugin_metadata(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> dict[str, Any]:
        return {
            "id": projection_ctx.plugin.id,
            "name": projection_ctx.plugin.name,
            "version": projection_ctx.plugin.version,
            "plugin_version_id": projection_ctx.version.id if projection_ctx.version else None,
            "installation_id": projection_ctx.installation.id if projection_ctx.installation else None,
            "artifact_ref": artifact_ref,
        }


class ToolProjector(BaseProjector):
    artifact_kind = "tool"
    default_dir = "tools"

    async def apply_install(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> ArtifactProjection:
        tool_spec = self.load_artifact(projection_ctx, artifact_ref)
        issues = self.validator.validate("tool_spec", tool_spec, raise_on_error=False)
        if issues:
            raise ValidationError(f"Invalid tool_spec for '{artifact_ref}': {issues[0].message}")
        get_registry().register(
            kind="tool",
            tenant_id=projection_ctx.ctx.tenant_id,
            workspace_id=projection_ctx.ctx.workspace_id,
            name=artifact_ref,
            version=projection_ctx.plugin.version,
            payload={
                "tool_spec": tool_spec,
                "source_kind": "plugin",
                "source_id": projection_ctx.plugin.id,
                "source_version": projection_ctx.version.id if projection_ctx.version else projection_ctx.plugin.version,
                "artifact_kind": "tool",
                "plugin": self._plugin_metadata(projection_ctx, artifact_ref),
            },
        )
        return ArtifactProjection("tool", artifact_ref, artifact_ref, None, {"tool_spec": tool_spec})

    async def apply_enable(self, projection_ctx: PluginProjectionContext, artifact: PluginInstalledArtifact, enabled: bool) -> None:
        await super().apply_enable(projection_ctx, artifact, enabled)
        if enabled:
            await self.apply_install(projection_ctx, artifact.artifact_ref)
        else:
            self._unregister(projection_ctx, artifact.artifact_ref)

    async def apply_uninstall(self, projection_ctx: PluginProjectionContext, artifact: PluginInstalledArtifact) -> None:
        await super().apply_uninstall(projection_ctx, artifact)
        self._unregister(projection_ctx, artifact.artifact_ref)

    def _unregister(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> None:
        reg = get_registry()
        for key, _ in reg.list(
            kind="tool",
            tenant_id=projection_ctx.ctx.tenant_id,
            workspace_id=projection_ctx.ctx.workspace_id,
            name=artifact_ref,
        ):
            reg.unregister(key)

    def _plugin_metadata(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> dict[str, Any]:
        return {
            "id": projection_ctx.plugin.id,
            "name": projection_ctx.plugin.name,
            "version": projection_ctx.plugin.version,
            "plugin_version_id": projection_ctx.version.id if projection_ctx.version else None,
            "installation_id": projection_ctx.installation.id if projection_ctx.installation else None,
            "artifact_ref": artifact_ref,
        }


class WorkflowNodeProjector(ToolProjector):
    artifact_kind = "workflow_node"
    artifact_kind_plural = "workflow_nodes"
    default_dir = "nodes"

    async def apply_install(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> ArtifactProjection:
        node_spec = self.load_artifact(projection_ctx, artifact_ref)
        issues = self.validator.validate("node_spec", node_spec, raise_on_error=False)
        if issues:
            raise ValidationError(f"Invalid node_spec for '{artifact_ref}': {issues[0].message}")
        get_registry().register(
            kind="workflow_node",
            tenant_id=projection_ctx.ctx.tenant_id,
            workspace_id=projection_ctx.ctx.workspace_id,
            name=artifact_ref,
            version=projection_ctx.plugin.version,
            payload={
                "node_spec": node_spec,
                "source_kind": "plugin",
                "source_id": projection_ctx.plugin.id,
                "source_version": projection_ctx.version.id if projection_ctx.version else projection_ctx.plugin.version,
                "artifact_kind": "workflow_node",
                "plugin": self._plugin_metadata(projection_ctx, artifact_ref),
            },
        )
        return ArtifactProjection("workflow_node", artifact_ref, artifact_ref, None, {"node_spec": node_spec})

    def _unregister(self, projection_ctx: PluginProjectionContext, artifact_ref: str) -> None:
        reg = get_registry()
        for key, _ in reg.list(
            kind="workflow_node",
            tenant_id=projection_ctx.ctx.tenant_id,
            workspace_id=projection_ctx.ctx.workspace_id,
            name=artifact_ref,
        ):
            reg.unregister(key)


class PluginProjectorRegistry:
    """Dispatch artifact refs to the projector for their kind."""

    def __init__(self) -> None:
        self._projectors: dict[str, BaseProjector] = {
            "skill": SkillProjector(),
            "mcp_server": MCPServerProjector(),
            "tool": ToolProjector(),
            "workflow_node": WorkflowNodeProjector(),
        }

    def projector_for(self, artifact_kind: str) -> BaseProjector:
        projector = self._projectors.get(artifact_kind)
        if not projector:
            raise ValidationError(f"Unsupported plugin artifact kind: {artifact_kind}")
        return projector

    async def project_all(
        self,
        projection_ctx: PluginProjectionContext,
        artifact_repo: PluginProjectionRepositoryPort,
    ) -> list[PluginInstalledArtifact]:
        projected: list[PluginInstalledArtifact] = []
        projected_refs: set[str] = set()
        for artifact_kind, export_key in (
            ("tool", "tools"),
            ("workflow_node", "workflow_nodes"),
            ("skill", "skills"),
            ("mcp_server", "mcp_servers"),
        ):
            refs = (projection_ctx.spec.get("exports") or {}).get(export_key) or []
            projector = self.projector_for(artifact_kind)
            for artifact_ref in refs:
                projection = await projector.apply_install(projection_ctx, str(artifact_ref))
                projected_refs.add(projection.artifact_ref)
                existing = artifact_repo.get_by_ref(
                    plugin_id=projection_ctx.plugin.id,
                    artifact_ref=projection.artifact_ref,
                )
                if existing:
                    item = existing
                    item.plugin_version_id = projection_ctx.version.id if projection_ctx.version else None
                    item.installation_id = projection_ctx.installation.id if projection_ctx.installation else None
                    item.artifact_kind = projection.artifact_kind
                    item.artifact_id = projection.artifact_id
                    item.artifact_version_id = projection.artifact_version_id
                    item.enabled = True
                    item.state = "enabled"
                    item.metadata_json = projection.metadata_json
                    item = artifact_repo.update(item)
                else:
                    item = artifact_repo.create(
                        PluginInstalledArtifact(
                            plugin_id=projection_ctx.plugin.id,
                            plugin_version_id=projection_ctx.version.id if projection_ctx.version else None,
                            installation_id=projection_ctx.installation.id if projection_ctx.installation else None,
                            artifact_kind=projection.artifact_kind,
                            artifact_ref=projection.artifact_ref,
                            artifact_id=projection.artifact_id,
                            artifact_version_id=projection.artifact_version_id,
                            enabled=True,
                            state="enabled",
                            metadata_json=projection.metadata_json,
                        )
                    )
                projected.append(item)
        if projection_ctx.installation:
            for artifact in artifact_repo.list_by_installation(projection_ctx.installation.id):
                if artifact.artifact_ref in projected_refs:
                    continue
                projector = self.projector_for(artifact.artifact_kind)
                await projector.apply_uninstall(projection_ctx, artifact)
                artifact_repo.update(artifact)
        return projected

    async def set_enabled(
        self,
        projection_ctx: PluginProjectionContext,
        artifact_repo: PluginProjectionRepositoryPort,
        enabled: bool,
    ) -> None:
        if not projection_ctx.installation:
            return
        for artifact in artifact_repo.list_by_installation(projection_ctx.installation.id):
            projector = self.projector_for(artifact.artifact_kind)
            await projector.apply_enable(projection_ctx, artifact, enabled)
            artifact_repo.update(artifact)

    async def uninstall(
        self,
        projection_ctx: PluginProjectionContext,
        artifact_repo: PluginProjectionRepositoryPort,
    ) -> None:
        if not projection_ctx.installation:
            return
        for artifact in artifact_repo.list_by_installation(projection_ctx.installation.id):
            projector = self.projector_for(artifact.artifact_kind)
            await projector.apply_uninstall(projection_ctx, artifact)
            artifact_repo.update(artifact)
