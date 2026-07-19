"""Plugin application service."""

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.kernel.commons.errors import ConflictError, NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.entitlements.features import FeatureRegistry, resolve_enabled_features
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_PLUGIN
from app.kernel.registry.deps import get_registry
from app.modules.plugin.application.ports import (
    PluginInstallationRepositoryPort,
    PluginInstallerPort,
    PluginProjectionRepositoryPort,
    PluginReleaseRepositoryPort,
    PluginRepositoryPort,
    PluginVersionRepositoryPort,
)
from app.modules.plugin.application.projectors import (
    PluginProjectionContext,
    PluginProjectorRegistry,
)
from app.modules.plugin.application.schemas import (
    PluginCreate,
    PluginInstallRequest,
    PluginUpdate,
    PluginVersionCreate,
)
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginRelease,
    PluginVersion,
)
from app.modules.plugin.runtime.loader import PluginRuntimeLoader
from app.modules.workflow.application.contracts import PublishedWorkflowUsagePort
from app.settings.settings import settings

logger = logging.getLogger(__name__)

class PluginService:
    """Plugin installation service."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        plugin_repo: PluginRepositoryPort,
        installation_repo: PluginInstallationRepositoryPort,
        installer: PluginInstallerPort,
        version_repo: PluginVersionRepositoryPort,
        release_repo: PluginReleaseRepositoryPort,
        artifact_repo: PluginProjectionRepositoryPort,
        workflow_usage: PublishedWorkflowUsagePort,
        approval_checkpoint_gateway: Any | None = None,
    ):
        """Initialize plugin market service.

        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.plugin_repo = plugin_repo
        self.installation_repo = installation_repo
        self.installer = installer
        self.settings = settings
        self.version_repo = version_repo
        self.release_repo = release_repo
        self.artifact_repo = artifact_repo
        self.workflow_usage = workflow_usage
        self.approval_checkpoint_gateway = approval_checkpoint_gateway
        self.projectors = PluginProjectorRegistry()

    @staticmethod
    def publish_status_for(plugin: Plugin) -> str:
        return plugin.publish_status

    @staticmethod
    def normalize_publish_status(publish_status: str | None, *, current: str = "draft") -> str:
        if publish_status is not None:
            normalized = publish_status.strip().lower()
            if normalized not in {"draft", "published", "archived"}:
                raise ValidationError(f"Invalid publish_status: {publish_status}")
            return normalized
        return current

    def _resolve_plugin_create_id(self, plugin_in: PluginCreate, **kwargs) -> str:
        """Resolve plugin id for create RBAC checks."""
        return plugin_in.name or f"new:{self.ctx.workspace_id}"

    def _infer_plugin_type(self, spec: dict[str, Any], explicit: str | None = None) -> str:
        value = (spec or {}).get("plugin_type")
        if value:
            return str(value)
        if explicit:
            return explicit
        exports = (spec or {}).get("exports") or {}
        kinds = [
            key
            for key, plugin_type in (
                ("skills", "skill"),
                ("mcp_servers", "mcp"),
                ("tools", "tool"),
                ("workflow_nodes", "workflow_node"),
            )
            if exports.get(key)
        ]
        if len(kinds) > 1:
            return "mixed"
        if kinds:
            mapping = {
                "skills": "skill",
                "mcp_servers": "mcp",
                "tools": "tool",
                "workflow_nodes": "workflow_node",
            }
            return mapping[kinds[0]]
        return "tool"

    def _require_publish_approval_if_needed(
        self,
        *,
        action: str,
        plugin: Plugin,
        version: PluginVersion,
        notes: str | None,
    ) -> None:
        if self.approval_checkpoint_gateway is None:
            return

        request = {
            "action": action,
            "resource_type": "plugin",
            "resource_ref": f"plugin:{plugin.id}",
            "risk_level": "high",
            "run_id": None,
            "task_id": None,
            "thread_id": None,
            "agent_id": None,
            "title": f"Approve {action}: plugin {plugin.name}",
            "details": {
                "subject_kind": "plugin",
                "subject_id": plugin.id,
                "plugin_name": plugin.name,
                "version_id": version.id,
                "version": version.version,
                "package_version": version.package_version,
                "scope": "workspace",
                "notes": notes,
            },
        }
        decision = self.approval_checkpoint_gateway.evaluate(self.ctx, request)
        if not bool(getattr(decision, "requires_approval", False)):
            return
        raise ValidationError(
            f"Approval required before {action}",
            details={
                "status": str(getattr(decision, "task_status", None) or "waiting_approval"),
                "reason": str(getattr(decision, "reason", "approval_required")),
                "policy_ref": getattr(decision, "policy_ref", None),
                "approval": dict(getattr(decision, "approval_payload", None) or {}),
                "request": request,
            },
        )

    def _artifact_summary(self, spec: dict[str, Any]) -> dict[str, Any]:
        exports = (spec or {}).get("exports") or {}
        return {
            "tools": list(exports.get("tools") or []),
            "workflow_nodes": list(exports.get("workflow_nodes") or []),
            "skills": list(exports.get("skills") or []),
            "mcp_servers": list(exports.get("mcp_servers") or []),
        }

    def _create_plugin_version(
        self,
        plugin: Plugin,
        *,
        package_version: str,
        spec: dict[str, Any],
        manifest: dict[str, Any],
        package_sha256: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PluginVersion:
        version = PluginVersion(
            plugin_id=plugin.id,
            version=self.version_repo.next_version_number(plugin.id),
            package_version=package_version,
            status="draft",
            spec_json=spec,
            manifest_json=manifest,
            package_sha256=package_sha256,
            artifact_summary_json=self._artifact_summary(spec),
            metadata_json=metadata or {},
            created_by=self.ctx.user_id,
        )
        version = self.version_repo.create(version)
        plugin.current_version_id = version.id
        plugin.version = package_version
        plugin.spec_json = spec
        plugin.manifest_json = manifest
        plugin.plugin_type = self._infer_plugin_type(spec, getattr(plugin, "plugin_type", None))
        plugin.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(plugin)
        return version

    def _get_plugin_version(self, version_id: str | None) -> PluginVersion | None:
        if not version_id:
            return None
        return self.version_repo.get_by_id(version_id)

    def _projection_context(
        self,
        *,
        plugin: Plugin,
        installation: PluginInstallation | None = None,
        version: PluginVersion | None = None,
    ) -> PluginProjectionContext:
        resolved_version = version or self._get_plugin_version(
            installation.plugin_version_id if installation else plugin.current_version_id
        )
        install_dir = self._install_dir_for(plugin_name=plugin.name, version=plugin.version)
        spec = (resolved_version.spec_json if resolved_version else plugin.spec_json) or {}
        return PluginProjectionContext(
            db=self.db,
            ctx=self.ctx,
            plugin=plugin,
            version=resolved_version,
            installation=installation,
            install_dir=install_dir,
            spec=spec,
        )

    def get_installation_for_plugin(self, plugin_id: str) -> PluginInstallation | None:
        """Return installation info for a plugin in this workspace."""
        return self.installation_repo.get_by_plugin(plugin_id)

    def list_installations_for_plugin(self, plugin_id: str) -> list[PluginInstallation]:
        return list(self.installation_repo.list_by_plugin(plugin_id))


    def _install_dir_for(self, *, plugin_name: str, version: str) -> Path:
        """Return install directory path for a plugin version in current scope."""
        root = Path(self.settings.plugins_dir).resolve()
        return root / "installed" / self.ctx.tenant_id / self.ctx.workspace_id / plugin_name / version

    def _packages_dir_for(self, *, plugin_name: str, version: str) -> Path:
        root = Path(self.settings.plugins_dir).resolve()
        return root / "packages" / self.ctx.tenant_id / self.ctx.workspace_id / plugin_name / version

    def _prune_empty_dirs(self, path: Path) -> None:
        current = path
        root = Path(self.settings.plugins_dir).resolve()
        while current != root and current.exists():
            if any(current.iterdir()):
                break
            current.rmdir()
            current = current.parent

    def _remove_plugin_files(self, *, plugin_name: str, version: str) -> None:
        install_dir = self._install_dir_for(plugin_name=plugin_name, version=version)
        packages_dir = self._packages_dir_for(plugin_name=plugin_name, version=version)
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)
            self._prune_empty_dirs(install_dir.parent)
        if packages_dir.exists():
            shutil.rmtree(packages_dir, ignore_errors=True)
            self._prune_empty_dirs(packages_dir.parent)

    def _remove_all_plugin_files(self, *, plugin_name: str) -> None:
        root = Path(self.settings.plugins_dir).resolve()
        for area in ("installed", "packages"):
            plugin_dir = root / area / self.ctx.tenant_id / self.ctx.workspace_id / plugin_name
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
                self._prune_empty_dirs(plugin_dir.parent)

    def _disable_all_plugin_versions(self, *, plugin: Plugin) -> None:
        for version in self.version_repo.list_by_plugin(plugin.id, limit=1_000, offset=0):
            self._sync_manifest_enabled(plugin_name=plugin.name, version=version.package_version, enabled=False)
            self._sync_registry_for_plugin(plugin_name=plugin.name, version=version.package_version, enabled=False)

    def _parse_version(self, value: str | None) -> tuple[int, int, int] | None:
        if not value:
            return None
        parts = value.split(".")
        numbers: list[int] = []
        for part in parts:
            digits = ""
            for ch in part:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if digits == "":
                numbers.append(0)
            else:
                numbers.append(int(digits))
        while len(numbers) < 3:
            numbers.append(0)
        return tuple(numbers[:3])

    def _collect_export_refs(self, spec: dict[str, Any]) -> tuple[set[str], set[str]]:
        if not isinstance(spec, dict):
            try:
                spec = json.loads(spec)
            except Exception:
                spec = {}
        exports = spec.get("exports") or {}
        tools = exports.get("tools") or []
        nodes = exports.get("workflow_nodes") or []
        return {str(item) for item in tools if item}, {str(item) for item in nodes if item}

    def _detect_registry_conflicts(
        self,
        *,
        tool_refs: set[str],
        node_refs: set[str],
        plugin_name: str,
    ) -> list[dict[str, Any]]:
        reg = get_registry()
        conflicts: list[dict[str, Any]] = []

        for tool_ref in sorted(tool_refs):
            found = reg.get_latest(
                kind="tool",
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                name=tool_ref,
            )
            if not found:
                continue
            _, payload = found
            plugin = (payload or {}).get("plugin") or {}
            if plugin and plugin.get("name") == plugin_name:
                continue
            conflicts.append(
                {
                    "kind": "tool",
                    "ref": tool_ref,
                    "existing_plugin": plugin.get("name") if plugin else None,
                }
            )

        for node_ref in sorted(node_refs):
            found = reg.get_latest(
                kind="workflow_node",
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                name=node_ref,
            )
            if not found:
                continue
            _, payload = found
            plugin = (payload or {}).get("plugin") or {}
            if plugin and plugin.get("name") == plugin_name:
                continue
            conflicts.append(
                {
                    "kind": "workflow_node",
                    "ref": node_ref,
                    "existing_plugin": plugin.get("name") if plugin else None,
                }
            )

        return conflicts

    def _check_conflicts(self, *, spec: dict[str, Any], plugin_name: str) -> None:
        tool_refs, node_refs = self._collect_export_refs(spec)
        conflicts = self._detect_registry_conflicts(
            tool_refs=tool_refs,
            node_refs=node_refs,
            plugin_name=plugin_name,
        )
        if conflicts:
            raise ValidationError(
                "Plugin export conflicts detected",
                {"conflicts": conflicts},
            )

    def _extract_workflow_refs(self, graph: dict[str, Any]) -> tuple[set[str], set[str]]:
        tool_refs: set[str] = set()
        node_refs: set[str] = set()
        if not isinstance(graph, dict):
            try:
                graph = json.loads(graph)
            except Exception:
                return tool_refs, node_refs
        graph_obj = graph.get("graph") or {}
        nodes = graph_obj.get("nodes") or []
        if not isinstance(nodes, list):
            return tool_refs, node_refs
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type")
            inputs = node.get("params") or node.get("input") or {}
            if not isinstance(inputs, dict):
                continue
            if node_type == "tool":
                tool_ref = inputs.get("tool_ref") or inputs.get("tool")
                if tool_ref:
                    tool_refs.add(str(tool_ref))
            if node_type == "node":
                node_ref = inputs.get("node_ref") or inputs.get("node")
                if node_ref:
                    node_refs.add(str(node_ref))
        return tool_refs, node_refs

    def _collect_published_workflow_refs(self) -> tuple[set[str], set[str]]:
        tool_refs: set[str] = set()
        node_refs: set[str] = set()
        for spec in self.workflow_usage.list_published_specs():
            wf_tools, wf_nodes = self._extract_workflow_refs(spec)
            tool_refs.update(wf_tools)
            node_refs.update(wf_nodes)
        return tool_refs, node_refs

    def _check_upgrade_compat(self, *, plugin: Plugin, next_spec: dict[str, Any]) -> None:
        current_spec = plugin.spec_json or {}
        current_tools, current_nodes = self._collect_export_refs(current_spec)
        if not current_tools and not current_nodes:
            return
        next_tools, next_nodes = self._collect_export_refs(next_spec)
        used_tools, used_nodes = self._collect_published_workflow_refs()

        removed_tools = (used_tools & current_tools) - next_tools
        removed_nodes = (used_nodes & current_nodes) - next_nodes
        if removed_tools or removed_nodes:
            raise ValidationError(
                "Plugin upgrade would break published workflows",
                {
                    "removed_tools": sorted(removed_tools),
                    "removed_nodes": sorted(removed_nodes),
                },
            )

    def _check_compatibility(self, spec: dict[str, Any]) -> None:
        compat = spec.get("compatibility") or {}
        min_v = self._parse_version(compat.get("min_platform_version"))
        max_v = self._parse_version(compat.get("max_platform_version"))
        platform_v = self._parse_version(self.settings.platform_version)
        if not platform_v:
            return
        if min_v and platform_v < min_v:
            raise ValidationError("Plugin requires a newer platform version")
        if max_v and platform_v > max_v:
            raise ValidationError("Plugin requires an older platform version")
        required_features = compat.get("requires_features") or []
        if required_features:
            try:
                feature_registry = FeatureRegistry.default()
                required_features = _normalize_feature_keys(feature_registry, required_features)
                platform_features = set(
                    resolve_enabled_features(
                        edition=self.settings.platform_edition,
                        entitlement_keys=self.settings.platform_entitlements or [],
                        registry=feature_registry,
                    )
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            missing = [feature for feature in required_features if feature not in platform_features]
            if missing:
                raise ValidationError(
                    "Plugin requires unavailable platform features",
                    {"missing_features": missing},
                )

    def _rollout_bucket(self, *, plugin_name: str, version: str) -> int:
        seed = f"{self.ctx.tenant_id}:{self.ctx.workspace_id}:{plugin_name}:{version}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % 100

    def _check_release_gate(self, *, spec: dict[str, Any], plugin_name: str) -> None:
        release = spec.get("release") or {}
        channel = (release.get("channel") or "stable").lower()
        rollout = release.get("rollout_percent")
        if rollout is None:
            return
        try:
            rollout_value = float(rollout)
        except (TypeError, ValueError):
            raise ValidationError("Invalid release.rollout_percent value")
        if rollout_value >= 100:
            return
        if rollout_value <= 0:
            raise ValidationError("Plugin rollout is closed", {"channel": channel, "rollout_percent": rollout_value})
        if channel == "stable":
            return
        version = str(spec.get("version") or "")
        bucket = self._rollout_bucket(plugin_name=plugin_name, version=version)
        if bucket >= rollout_value:
            raise ValidationError(
                "Plugin not in rollout cohort",
                {"channel": channel, "rollout_percent": rollout_value},
            )

    def _validate_runtime_manifest(self, manifest: dict[str, Any]) -> None:
        runtime = (manifest or {}).get("runtime") or {}
        if not runtime:
            return
        runtime_type = runtime.get("type") or "http"
        if runtime_type != "http":
            return
        base_url = runtime.get("base_url")
        if not base_url:
            raise ValidationError("Plugin manifest missing runtime.base_url")
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1") and not self.settings.plugin_runtime_allow_localhost:
            raise ValidationError("Plugin runtime must run out-of-process (localhost not allowed)")

    def _sync_manifest_enabled(self, *, plugin_name: str, version: str, enabled: bool) -> None:
        """Best-effort: keep filesystem manifest enabled flag in sync."""
        install_dir = self._install_dir_for(plugin_name=plugin_name, version=version)
        manifest_path = install_dir / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["enabled"] = bool(enabled)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            # Do not fail requests on filesystem issues
            return

    def _sync_registry_for_plugin(self, *, plugin_name: str, version: str, enabled: bool) -> None:
        """Sync in-process registry for a plugin version (tools/nodes + plugin record)."""
        reg = get_registry()

        # remove all tool artifacts belonging to this plugin+version in this scope
        items = reg.list(kind="tool", tenant_id=self.ctx.tenant_id, workspace_id=self.ctx.workspace_id)
        for key, payload in items:
            plugin = (payload or {}).get("plugin") or {}
            if plugin.get("name") == plugin_name and plugin.get("version") == version:
                reg.unregister(key)

        # remove plugin artifacts for all supported lookup names
        plugin_items = reg.list(
            kind="plugin",
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
        )
        for key, payload in plugin_items:
            payload_plugin = (payload or {}).get("plugin") or {}
            if key.version == version and (
                key.name == plugin_name
                or key.name.endswith(f":{plugin_name}:{version}")
                or key.name.endswith(f":{plugin_name}")
                or payload_plugin.get("name") == plugin_name
                or (payload or {}).get("source_id") == plugin_name
            ):
                reg.unregister(key)

        # remove all workflow node artifacts belonging to this plugin+version in this scope
        node_items = reg.list(kind="workflow_node", tenant_id=self.ctx.tenant_id, workspace_id=self.ctx.workspace_id)
        for key, payload in node_items:
            plugin = (payload or {}).get("plugin") or {}
            if plugin.get("name") == plugin_name and plugin.get("version") == version:
                reg.unregister(key)

        if enabled:
            # reload from filesystem (best-effort)
            PluginRuntimeLoader().load_all()

    @rbac_guard(RESOURCE_PLUGIN, "create", resource_id_resolver=_resolve_plugin_create_id)
    async def create_plugin(self, plugin_in: PluginCreate) -> Plugin:
        """Create a new plugin.

        Args:
            plugin_in: Plugin creation schema.

        Returns:
            Created Plugin instance.

        Raises:
            ValidationError: If plugin name and version combination already exists.
        """
        # Check if name and version combination already exists
        existing = self.plugin_repo.get_by_name_version(plugin_in.name, plugin_in.version)
        if existing:
            raise ValidationError(
                f"Plugin '{plugin_in.name}' version '{plugin_in.version}' already exists"
            )

        plugin = Plugin(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=plugin_in.name,
            version=plugin_in.version,
            publisher=plugin_in.publisher,
            plugin_type=self._infer_plugin_type(plugin_in.spec_json, plugin_in.plugin_type),
            status="active",
            description=plugin_in.description,
            spec_json=plugin_in.spec_json,
            manifest_json=plugin_in.manifest_json or {},
            metadata_json=plugin_in.metadata_json,
            publish_status="draft",
            created_by=self.ctx.user_id,
        )

        plugin = self.plugin_repo.create(plugin)
        version = self._create_plugin_version(
            plugin,
            package_version=plugin_in.version,
            spec=plugin_in.spec_json,
            manifest=plugin_in.manifest_json or {},
            metadata=plugin_in.metadata_json,
        )
        plugin.current_version_id = version.id
        self.db.commit()
        self.db.refresh(plugin)
        logger.info(
            "plugin.create",
            extra={
                "plugin_name": plugin.name,
                "version": plugin.version,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )
        return plugin

    @rbac_guard(RESOURCE_PLUGIN, "read", resource_id_arg="plugin_id")
    async def get_plugin(self, plugin_id: str) -> Plugin:
        """Get plugin by ID.

        Args:
            plugin_id: Plugin ID.

        Returns:
            Plugin instance.

        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = self.plugin_repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundError(f"Plugin not found: {plugin_id}")
        return plugin



    @workspace_guard("read")
    async def list_plugins(
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
        return self.plugin_repo.list(
            published_only=published_only,
            plugin_type=plugin_type,
            limit=limit,
            offset=offset,
        )

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def update_plugin(self, plugin_id: str, plugin_in: PluginUpdate) -> Plugin:
        """Update plugin.

        Args:
            plugin_id: Plugin ID.
            plugin_in: Plugin update schema.

        Returns:
            Updated Plugin instance.

        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = await self.get_plugin(plugin_id)

        if plugin_in.description is not None:
            plugin.description = plugin_in.description

        if plugin_in.plugin_type is not None:
            plugin.plugin_type = plugin_in.plugin_type

        if plugin_in.status is not None:
            plugin.status = plugin_in.status

        if plugin_in.spec_json is not None:
            plugin.spec_json = plugin_in.spec_json

        if plugin_in.manifest_json is not None:
            plugin.manifest_json = plugin_in.manifest_json

        if plugin_in.metadata_json is not None:
            plugin.metadata_json = plugin_in.metadata_json

        plugin.publish_status = self.normalize_publish_status(
            plugin_in.publish_status,
            current=plugin.publish_status,
        )

        plugin.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(plugin)
        logger.info(
            "plugin.update",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )
        return plugin

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def create_version(self, plugin_id: str, data: PluginVersionCreate) -> PluginVersion:
        plugin = await self.get_plugin(plugin_id)
        spec = data.spec_json
        manifest = data.manifest_json
        package_version = data.version or str(spec.get("version") or plugin.version)
        plugin.plugin_type = self._infer_plugin_type(spec, plugin.plugin_type)
        version = self._create_plugin_version(
            plugin,
            package_version=package_version,
            spec=spec,
            manifest=manifest,
            metadata=data.metadata_json,
        )
        return version

    @rbac_guard(RESOURCE_PLUGIN, "read", resource_id_arg="plugin_id")
    async def list_versions(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> list[PluginVersion]:
        await self.get_plugin(plugin_id)
        return self.version_repo.list_by_plugin(plugin_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_PLUGIN, "read", resource_id_arg="plugin_id")
    async def list_releases(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> list[PluginRelease]:
        await self.get_plugin(plugin_id)
        return self.release_repo.list_by_plugin(plugin_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def publish_version(self, plugin_id: str, version_id: str, *, notes: str | None = None) -> Plugin:
        plugin = await self.get_plugin(plugin_id)
        version = self.version_repo.get_by_id(version_id)
        if not version or version.plugin_id != plugin.id:
            raise NotFoundError(f"Plugin version not found: {version_id}")
        self._require_publish_approval_if_needed(
            action="publish",
            plugin=plugin,
            version=version,
            notes=notes,
        )
        previous = plugin.published_version_id
        previous_version = self._get_plugin_version(previous)
        version.status = "published"
        self.version_repo.update(version)
        release = PluginRelease(
            plugin_id=plugin.id,
            plugin_version_id=version.id,
            action="publish",
            status="published",
            from_version_id=previous,
            to_version_id=version.id,
            notes=notes,
            created_by=self.ctx.user_id,
        )
        self.release_repo.create(release)
        plugin.published_version_id = version.id
        plugin.current_version_id = version.id
        plugin.version = version.package_version
        plugin.spec_json = version.spec_json
        plugin.manifest_json = version.manifest_json
        plugin.plugin_type = self._infer_plugin_type(version.spec_json, plugin.plugin_type)
        plugin.publish_status = "published"
        plugin.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(plugin)
        if previous_version and previous_version.package_version != version.package_version:
            self._sync_manifest_enabled(plugin_name=plugin.name, version=previous_version.package_version, enabled=False)
            self._sync_registry_for_plugin(plugin_name=plugin.name, version=previous_version.package_version, enabled=False)
        self._sync_manifest_enabled(plugin_name=plugin.name, version=version.package_version, enabled=True)
        installation = self.installation_repo.get_by_plugin(plugin.id)
        if installation:
            installation.plugin_version_id = version.id
            installation = self.installation_repo.update(installation)
            await self.projectors.project_all(
                self._projection_context(plugin=plugin, installation=installation, version=version),
                self.artifact_repo,
            )
            self._sync_plugin_capability_payload(plugin=plugin, version=version, installation=installation)
        return plugin

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def rollback_version(self, plugin_id: str, version_id: str, *, notes: str | None = None) -> Plugin:
        plugin = await self.get_plugin(plugin_id)
        version = self.version_repo.get_by_id(version_id)
        if not version or version.plugin_id != plugin.id:
            raise NotFoundError(f"Plugin version not found: {version_id}")
        self._require_publish_approval_if_needed(
            action="rollback",
            plugin=plugin,
            version=version,
            notes=notes,
        )
        previous = plugin.published_version_id
        previous_version = self._get_plugin_version(previous)
        release = PluginRelease(
            plugin_id=plugin.id,
            plugin_version_id=version.id,
            action="rollback",
            status="rolled_back",
            from_version_id=previous,
            to_version_id=version.id,
            notes=notes,
            created_by=self.ctx.user_id,
        )
        self.release_repo.create(release)
        plugin.published_version_id = version.id
        plugin.current_version_id = version.id
        plugin.version = version.package_version
        plugin.spec_json = version.spec_json
        plugin.manifest_json = version.manifest_json
        plugin.plugin_type = self._infer_plugin_type(version.spec_json, plugin.plugin_type)
        plugin.publish_status = "published"
        plugin.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(plugin)
        if previous_version and previous_version.package_version != version.package_version:
            self._sync_manifest_enabled(plugin_name=plugin.name, version=previous_version.package_version, enabled=False)
            self._sync_registry_for_plugin(plugin_name=plugin.name, version=previous_version.package_version, enabled=False)
        self._sync_manifest_enabled(plugin_name=plugin.name, version=version.package_version, enabled=True)
        installation = self.installation_repo.get_by_plugin(plugin.id)
        if installation:
            installation.plugin_version_id = version.id
            installation = self.installation_repo.update(installation)
            await self.projectors.project_all(
                self._projection_context(plugin=plugin, installation=installation, version=version),
                self.artifact_repo,
            )
            self._sync_plugin_capability_payload(plugin=plugin, version=version, installation=installation)
        return plugin

    @rbac_guard(RESOURCE_PLUGIN, "delete", resource_id_arg="plugin_id")
    async def delete_plugin(self, plugin_id: str) -> None:
        """Delete plugin.

        Args:
            plugin_id: Plugin ID.

        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = await self.get_plugin(plugin_id)

        # Delete associated installations
        installations = self.installation_repo.list_by_workspace(limit=1000, offset=0)
        for installation in installations:
            if installation.plugin_id == plugin_id:
                self.db.delete(installation)

        self.db.delete(plugin)
        self.db.commit()
        logger.info(
            "plugin.delete",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def install_plugin(self, plugin_id: str, install_request: PluginInstallRequest) -> PluginInstallation:
        """Install a plugin.

        Args:
            plugin_id: Plugin ID.
            install_request: Installation request.

        Returns:
            Created PluginInstallation instance.

        Raises:
            NotFoundError: If plugin not found.
            ValidationError: If plugin is already installed.
        """
        plugin = await self.get_plugin(plugin_id)

        # Check if already installed
        existing = self.installation_repo.get_by_plugin(plugin_id)
        if existing:
            raise ValidationError(f"Plugin '{plugin.name}' is already installed")
        if not plugin.published_version_id:
            raise ValidationError("Plugin must be published before installation")

        # Create installation
        installation = PluginInstallation(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            plugin_id=plugin_id,
            plugin_version_id=plugin.published_version_id,
            installed_by=self.ctx.user_id,
            config_json=install_request.config_json,
            enabled=True,
            state="installed",
        )

        installation = self.installation_repo.create(installation)

        # Update plugin installed_count
        plugin.installed_count += 1
        self.db.commit()
        self.db.refresh(plugin)

        logger.info(
            "plugin.install_record",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

        return installation

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def install_plugin_package(
        self,
        plugin_id: str,
        package_bytes: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> dict:
        """Install plugin package bytes into filesystem and register into runtime registry.

        This does NOT change DB schema. It will:
        1) validate plugin exists
        2) install package into plugins_dir
        3) mark installation record (creates if absent)

        Returns:
            dict with install_dir, sha256, manifest, spec
        """
        plugin = await self.get_plugin(plugin_id)
        manifest, spec = self.installer.inspect_package(package_bytes)
        spec_name = spec.get("name")
        spec_version = spec.get("version")
        if spec_name and spec_name != plugin.name:
            raise ValidationError("Plugin package name mismatch")
        if spec_version and spec_version != plugin.version:
            raise ValidationError("Plugin package version mismatch")
        plugin.plugin_type = self._infer_plugin_type(spec, plugin.plugin_type)
        self._check_compatibility(spec)
        self._check_release_gate(spec=spec, plugin_name=plugin.name)
        self._validate_runtime_manifest(manifest)
        self._check_conflicts(spec=spec, plugin_name=plugin.name)

        paths = self.installer.install_from_bytes(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            plugin_name=plugin.name,
            version=plugin.version,
            package_bytes=package_bytes,
            expected_sha256=expected_sha256,
        )
        digest = hashlib.sha256(package_bytes).hexdigest()
        version = self._create_plugin_version(
            plugin,
            package_version=plugin.version,
            spec=spec,
            manifest=manifest,
            package_sha256=digest,
            metadata={"package_path": str(paths.package_path)},
        )

        # ensure installation row exists
        existing = self.installation_repo.get_by_plugin(plugin_id)
        if not existing:
            installation = PluginInstallation(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                plugin_id=plugin_id,
                plugin_version_id=version.id,
                installed_by=self.ctx.user_id,
                config_json={"enabled": True},
                enabled=True,
                state="installed",
            )
            installation = self.installation_repo.create(installation)
            plugin.installed_count += 1
            self.db.commit()
            self.db.refresh(plugin)
        else:
            cfg = existing.config_json or {}
            cfg["enabled"] = True
            existing.config_json = cfg
            existing.plugin_version_id = version.id
            existing.enabled = True
            existing.state = "installed"
            installation = self.installation_repo.update(existing)
            self.db.commit()

        plugin.spec_json = spec
        plugin.manifest_json = manifest
        plugin.current_version_id = version.id
        plugin.published_version_id = version.id
        plugin.publish_status = "published"
        plugin.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(plugin)

        await self.projectors.project_all(
            self._projection_context(plugin=plugin, installation=installation, version=version),
            self.artifact_repo,
        )
        self._sync_plugin_capability_payload(plugin=plugin, version=version, installation=installation)

        return {
            "install_dir": str(paths.install_dir),
            "package_path": str(paths.package_path),
            "manifest_path": str(paths.manifest_path),
            "spec_path": str(paths.spec_path),
        }

    @workspace_guard("write")
    async def upload_plugin_package(
        self,
        package_bytes: bytes,
        *,
        mode: str = "auto",
        expected_sha256: str | None = None,
    ) -> dict:
        """Create, upgrade, or reinstall a plugin from package bytes."""
        normalized_mode = (mode or "auto").strip().lower()
        if normalized_mode not in {"auto", "reinstall"}:
            raise ValidationError("Invalid plugin package upload mode")

        manifest, spec = self.installer.inspect_package(package_bytes)
        package_name = str(spec.get("name") or "").strip()
        package_version = str(spec.get("version") or "").strip()
        if not package_name:
            raise ValidationError("Plugin package missing name")
        if not package_version:
            raise ValidationError("Plugin package missing version")

        self._check_compatibility(spec)
        self._check_release_gate(spec=spec, plugin_name=package_name)
        self._validate_runtime_manifest(manifest)
        self._check_conflicts(spec=spec, plugin_name=package_name)

        existing = self.plugin_repo.get_by_name(package_name)
        if existing:
            if existing.version == package_version:
                if normalized_mode != "reinstall":
                    raise ConflictError(
                        "Plugin package version already exists",
                        details={
                            "reason": "same_version_exists",
                            "plugin_id": existing.id,
                            "name": package_name,
                            "version": package_version,
                        },
                    )
                install_result = await self.install_plugin_package(
                    existing.id,
                    package_bytes,
                    expected_sha256=expected_sha256,
                )
                action = "reinstalled"
            else:
                install_result = await self.upgrade_plugin_package(
                    existing.id,
                    package_bytes,
                    expected_sha256=expected_sha256,
                )
                action = "upgraded"
            plugin = await self.get_plugin(existing.id)
            return {"action": action, "plugin": plugin, "install": install_result}

        plugin = Plugin(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=package_name,
            version=package_version,
            publisher=str(spec.get("publisher") or "soit"),
            plugin_type=self._infer_plugin_type(spec, spec.get("plugin_type")),
            status="active",
            description=spec.get("description") if isinstance(spec.get("description"), str) else None,
            spec_json=spec,
            manifest_json=manifest,
            metadata_json={"package_sha256": hashlib.sha256(package_bytes).hexdigest()},
            publish_status="published",
            created_by=self.ctx.user_id,
        )
        plugin = self.plugin_repo.create(plugin)
        install_result = await self.install_plugin_package(
            plugin.id,
            package_bytes,
            expected_sha256=expected_sha256,
        )
        plugin = await self.get_plugin(plugin.id)
        return {"action": "created", "plugin": plugin, "install": install_result}

    @rbac_guard(RESOURCE_PLUGIN, "delete", resource_id_arg="plugin_id")
    async def uninstall_plugin(self, plugin_id: str) -> None:
        """Uninstall a plugin from this workspace."""
        plugin = await self.get_plugin(plugin_id)

        installation = self.installation_repo.get_by_plugin(plugin_id)
        if installation:
            await self.projectors.uninstall(
                self._projection_context(plugin=plugin, installation=installation),
                self.artifact_repo,
            )
            self.db.delete(installation)
            if plugin.installed_count > 0:
                plugin.installed_count -= 1
            plugin.updated_at = utc_now()
            self.db.commit()

        self._disable_all_plugin_versions(plugin=plugin)
        self._remove_all_plugin_files(plugin_name=plugin.name)

        logger.info(
            "plugin.uninstall",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def upgrade_plugin_package(
        self,
        plugin_id: str,
        package_bytes: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> dict:
        """Upgrade an installed plugin by replacing its package/version."""
        plugin = await self.get_plugin(plugin_id)

        manifest, spec = self.installer.inspect_package(package_bytes)
        spec_name = spec.get("name")
        spec_version = spec.get("version")
        if spec_name and spec_name != plugin.name:
            raise ValidationError("Plugin package name mismatch")
        if not spec_version:
            raise ValidationError("Plugin package missing version")
        plugin.plugin_type = self._infer_plugin_type(spec, plugin.plugin_type)
        self._check_compatibility(spec)
        self._check_release_gate(spec=spec, plugin_name=plugin.name)
        self._validate_runtime_manifest(manifest)
        self._check_conflicts(spec=spec, plugin_name=plugin.name)
        self._check_upgrade_compat(plugin=plugin, next_spec=spec)

        old_version = plugin.version
        plugin.version = spec_version
        plugin.spec_json = spec
        plugin.manifest_json = manifest
        plugin.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(plugin)

        paths = self.installer.install_from_bytes(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            plugin_name=plugin.name,
            version=spec_version,
            package_bytes=package_bytes,
            expected_sha256=expected_sha256,
        )
        version = self._create_plugin_version(
            plugin,
            package_version=spec_version,
            spec=spec,
            manifest=manifest,
            package_sha256=hashlib.sha256(package_bytes).hexdigest(),
            metadata={"package_path": str(paths.package_path)},
        )
        installation = self.installation_repo.get_by_plugin(plugin_id)
        if installation:
            cfg = installation.config_json or {}
            cfg["enabled"] = True
            installation.config_json = cfg
            installation.plugin_version_id = version.id
            installation.enabled = True
            installation.state = "installed"
            installation = self.installation_repo.update(installation)
            await self.projectors.project_all(
                self._projection_context(plugin=plugin, installation=installation, version=version),
                self.artifact_repo,
            )
            self._sync_plugin_capability_payload(plugin=plugin, version=version, installation=installation)

        if old_version != spec_version:
            self._sync_registry_for_plugin(plugin_name=plugin.name, version=old_version, enabled=False)
            self._sync_manifest_enabled(plugin_name=plugin.name, version=old_version, enabled=False)

        logger.info(
            "plugin.upgrade",
            extra={
                "plugin_id": plugin_id,
                "old_version": old_version,
                "new_version": spec_version,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

        return {
            "install_dir": str(paths.install_dir),
            "package_path": str(paths.package_path),
            "manifest_path": str(paths.manifest_path),
            "spec_path": str(paths.spec_path),
        }

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> PluginInstallation:
        """Enable/disable a plugin installation in this workspace.

        State is stored in:
        - DB: PluginInstallation.config_json["enabled"]
        - FS: <install_dir>/manifest.json["enabled"] (for restart-safe runtime loader)
        """
        plugin = await self.get_plugin(plugin_id)

        installation = self.installation_repo.get_by_plugin(plugin_id)
        if not installation:
            raise NotFoundError("Plugin is not installed.")

        cfg = installation.config_json or {}
        cfg["enabled"] = bool(enabled)
        installation.config_json = cfg
        installation.enabled = bool(enabled)
        installation.state = "installed" if enabled else "disabled"
        installation = self.installation_repo.update(installation)
        self.db.commit()
        self.db.refresh(installation)

        # keep filesystem manifest in-sync for restart-safe loader
        self._sync_manifest_enabled(plugin_name=plugin.name, version=plugin.version, enabled=bool(enabled))

        # sync runtime registry (tools + plugin record)
        self._sync_registry_for_plugin(plugin_name=plugin.name, version=plugin.version, enabled=bool(enabled))
        await self.projectors.set_enabled(
            self._projection_context(plugin=plugin, installation=installation),
            self.artifact_repo,
            bool(enabled),
        )
        self._sync_plugin_capability_payload(
            plugin=plugin,
            version=self._get_plugin_version(installation.plugin_version_id),
            installation=installation,
        )

        logger.info(
            "plugin.enabled",
            extra={
                "plugin_id": plugin_id,
                "enabled": bool(enabled),
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

        return installation

    def _sync_plugin_capability_payload(
        self,
        *,
        plugin: Plugin,
        version: PluginVersion | None,
        installation: PluginInstallation | None,
    ) -> None:
        reg = get_registry()
        tools: list[str] = []
        nodes: list[str] = []
        if installation and installation.enabled:
            artifacts = self.artifact_repo.list_by_installation(installation.id)
            for artifact in artifacts:
                if not artifact.enabled:
                    continue
                if artifact.artifact_kind == "tool":
                    tools.append(artifact.artifact_ref)
                elif artifact.artifact_kind == "workflow_node":
                    nodes.append(artifact.artifact_ref)
                elif artifact.artifact_kind == "mcp_server":
                    for capability in self._capabilities_for_artifact(artifact):
                        if capability["kind"] == "mcp_tool":
                            tools.append(capability["ref"])
        payload = {
            "install_dir": str(self._install_dir_for(plugin_name=plugin.name, version=plugin.version)),
            "manifest": (version.manifest_json if version else plugin.manifest_json) or {},
            "spec": (version.spec_json if version else plugin.spec_json) or {},
            "tools": tools,
            "nodes": nodes,
            "source_kind": "plugin",
            "source_id": plugin.id,
            "source_version": version.id if version else plugin.version,
            "installation_id": installation.id if installation else None,
        }
        for name in {plugin.name, f"{plugin.publisher}:{plugin.name}", f"plugin:{plugin.publisher}:{plugin.name}:{plugin.version}"}:
            reg.register(
                kind="plugin",
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                name=name,
                version=plugin.version,
                payload=payload,
            )

    @workspace_guard("read")
    async def list_artifacts(
        self,
        *,
        plugin_id: str | None = None,
        artifact_kind: str | None = None,
        enabled: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PluginInstalledArtifact]:
        if plugin_id:
            await self.get_plugin(plugin_id)
        return self.artifact_repo.list(
            plugin_id=plugin_id,
            artifact_kind=artifact_kind,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )

    @workspace_guard("read")
    async def list_capabilities(
        self,
        *,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        artifacts = self.artifact_repo.list(enabled=True, limit=1_000, offset=0)
        capabilities: list[dict[str, Any]] = []
        for artifact in artifacts:
            capabilities.extend(self._capabilities_for_artifact(artifact))
        if kind:
            capabilities = [item for item in capabilities if item["kind"] == kind]
        return capabilities[offset : offset + limit]

    def _capabilities_for_artifact(self, artifact: PluginInstalledArtifact) -> list[dict[str, Any]]:
        base = {
            "source_kind": "plugin",
            "source_id": artifact.plugin_id,
            "source_version": artifact.plugin_version_id,
            "artifact_kind": artifact.artifact_kind,
            "plugin_id": artifact.plugin_id,
            "plugin_version_id": artifact.plugin_version_id,
            "installation_id": artifact.installation_id,
        }
        if artifact.artifact_kind == "skill":
            return [
                {
                    **base,
                    "ref": artifact.artifact_ref,
                    "kind": "skill",
                    "name": artifact.artifact_ref.split(":", 1)[-1],
                    "metadata_json": artifact.metadata_json,
                }
            ]
        if artifact.artifact_kind == "tool":
            tool_spec = (artifact.metadata_json or {}).get("tool_spec") or {}
            return [
                {
                    **base,
                    "ref": artifact.artifact_ref,
                    "kind": "tool",
                    "name": tool_spec.get("name") or artifact.artifact_ref.split(":")[-1],
                    "metadata_json": artifact.metadata_json,
                }
            ]
        if artifact.artifact_kind == "workflow_node":
            node_spec = (artifact.metadata_json or {}).get("node_spec") or {}
            return [
                {
                    **base,
                    "ref": artifact.artifact_ref,
                    "kind": "workflow_node",
                    "name": node_spec.get("name") or artifact.artifact_ref.split(":")[-1],
                    "metadata_json": artifact.metadata_json,
                }
            ]
        if artifact.artifact_kind == "mcp_server":
            mcp = (artifact.metadata_json or {}).get("mcp_server") or {}
            server_name = mcp.get("name") or artifact.artifact_ref.split(":", 1)[-1]
            items: list[dict[str, Any]] = [
                {
                    **base,
                    "ref": artifact.artifact_ref,
                    "kind": "mcp_server",
                    "name": server_name,
                    "metadata_json": artifact.metadata_json,
                }
            ]
            capabilities = mcp.get("capabilities_json") or {}
            for tool in capabilities.get("tools") or []:
                if isinstance(tool, dict):
                    tool_name = str(tool.get("name") or tool.get("id") or "").strip()
                    if tool_name:
                        items.append(
                            {
                                **base,
                                "ref": f"mcp_tool:{server_name}:{tool_name}",
                                "kind": "mcp_tool",
                                "name": tool_name,
                                "metadata_json": {**artifact.metadata_json, "capability": tool},
                            }
                        )
            for resource in capabilities.get("resources") or []:
                if isinstance(resource, dict):
                    resource_name = str(resource.get("name") or resource.get("id") or "").strip()
                    if resource_name:
                        items.append(
                            {
                                **base,
                                "ref": f"mcp_resource:{server_name}:{resource_name}",
                                "kind": "mcp_resource",
                                "name": resource_name,
                                "metadata_json": {**artifact.metadata_json, "capability": resource},
                            }
                        )
            return items
        return []


def _normalize_feature_keys(registry: FeatureRegistry, keys: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for key in keys:
        value = str(key).strip()
        if not value or value in seen:
            continue
        registry.get(value)
        normalized.append(value)
        seen.add(value)
    return normalized
