""" loader

Runtime loader for installed plugins (filesystem-based).

It rebuilds the in-process registry on process start or on-demand.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.kernel.specs.validator import SpecValidator
from app.settings.settings import settings

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LoadedPlugin:
    tenant_id: str
    workspace_id: str
    name: str
    version: str
    install_dir: Path
    tool_refs: list[str]
    node_refs: list[str]


class PluginRuntimeLoader:
    """Load installed plugins from filesystem into registry."""

    def __init__(self, *, validator: SpecValidator | None = None):
        self.validator = validator or SpecValidator()

    def _root(self) -> Path:
        return Path(settings.plugins_dir).resolve() / "installed"

    def _runtime_allowed(self, manifest: dict[str, Any]) -> bool:
        runtime = (manifest or {}).get("runtime") or {}
        runtime_type = runtime.get("type") or "http"
        if runtime_type != "http":
            return False
        base_url = runtime.get("base_url")
        if not base_url:
            return False
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1") and not settings.plugin_runtime_allow_localhost:
            return False
        return True

    def load_all(self) -> list[LoadedPlugin]:
        root = self._root()
        if not root.exists():
            return []

        loaded: list[LoadedPlugin] = []
        reg = get_registry()

        # expected layout:
        #   <plugins_dir>/installed/<tenant>/<workspace>/<plugin>/<version>/{manifest.json,spec.json,files/}
        for manifest_path in root.glob("**/manifest.json"):
            install_dir = manifest_path.parent
            try:
                spec_path = install_dir / "spec.json"
                if not spec_path.exists():
                    continue

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("enabled") is False:
                    continue
                if not self._runtime_allowed(manifest):
                    logger.warning("plugin.load_blocked_runtime", extra={"install_dir": str(install_dir)})
                    continue
                spec = json.loads(spec_path.read_text(encoding="utf-8"))

                issues = self.validator.validate("plugin_spec", spec, raise_on_error=False)
                if issues:
                    raise ValidationError(
                        f"Invalid plugin_spec at {spec_path}",
                        {"issues": [issue.__dict__ for issue in issues]},
                    )

                # parse scope from path parts
                parts = install_dir.relative_to(root).parts
                if len(parts) < 4:
                    continue
                tenant_id, workspace_id, plugin_name, version = parts[0], parts[1], parts[2], parts[3]

                # load exported tools
                files_dir = install_dir / "files"
                tool_refs: list[str] = []
                exported_tools = (spec.get("exports") or {}).get("tools") or []
                for tool_ref in exported_tools:
                    tool_spec_path = files_dir / "tools" / f"{tool_ref.split(':',2)[2]}.json"
                    if not tool_spec_path.exists():
                        continue
                    try:
                        tool_spec = json.loads(tool_spec_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    tool_issues = self.validator.validate("tool_spec", tool_spec, raise_on_error=False)
                    if tool_issues:
                        continue
                    reg.register(
                        kind="tool",
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        name=tool_ref,
                        version=version,
                        payload={
                            "tool_spec": tool_spec,
                            "plugin": {"name": plugin_name, "version": version},
                        },
                    )
                    tool_refs.append(tool_ref)

                # load exported workflow nodes
                node_refs: list[str] = []
                exported_nodes = (spec.get("exports") or {}).get("workflow_nodes") or []
                node_artifacts = (spec.get("artifacts") or {}).get("workflow_nodes") or {}
                for node_ref in exported_nodes:
                    node_spec_path = None
                    if isinstance(node_artifacts, dict) and node_ref in node_artifacts:
                        node_spec_path = install_dir / node_artifacts[node_ref]
                    else:
                        node_name = node_ref.split(":", 2)[2] if ":" in node_ref else node_ref
                        node_spec_path = files_dir / "nodes" / f"{node_name}.json"
                    if not node_spec_path.exists():
                        continue
                    try:
                        node_spec = json.loads(node_spec_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    node_issues = self.validator.validate("node_spec", node_spec, raise_on_error=False)
                    if node_issues:
                        continue
                    reg.register(
                        kind="workflow_node",
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        name=node_ref,
                        version=version,
                        payload={
                            "node_spec": node_spec,
                            "plugin": {"name": plugin_name, "version": version},
                        },
                    )
                    node_refs.append(node_ref)

                reg.register(
                    kind="plugin",
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    name=plugin_name,
                    version=version,
                    payload={
                        "install_dir": str(install_dir),
                        "manifest": manifest,
                        "spec": spec,
                        "tools": tool_refs,
                        "nodes": node_refs,
                    },
                )

                loaded.append(
                    LoadedPlugin(
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        name=plugin_name,
                        version=version,
                        install_dir=install_dir,
                        tool_refs=tool_refs,
                        node_refs=node_refs,
                    )
                )
                logger.info(
                    "plugin.load",
                    extra={
                        "plugin_name": plugin_name,
                        "version": version,
                        "tenant_id": tenant_id,
                        "workspace_id": workspace_id,
                        "tool_count": len(tool_refs),
                        "node_count": len(node_refs),
                    },
                )
            except Exception:
                # Loader should be best-effort; do not crash the app on a single bad plugin.
                logger.exception("plugin.load_failed", extra={"install_dir": str(install_dir)})
                continue

        return loaded
