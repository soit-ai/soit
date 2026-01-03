""" loader

Runtime loader for installed plugins (filesystem-based).

It rebuilds the in-process registry on process start or on-demand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.kernel.specs.validator import SpecValidator
from app.settings.settings import settings


@dataclass(frozen=True)
class LoadedPlugin:
    tenant_id: str
    workspace_id: str
    name: str
    version: str
    install_dir: Path
    tool_refs: List[str]


class PluginRuntimeLoader:
    """Load installed plugins from filesystem into registry."""

    def __init__(self, *, validator: Optional[SpecValidator] = None):
        self.validator = validator or SpecValidator()

    def _root(self) -> Path:
        return Path(settings.plugins_dir).resolve() / "installed"

    def load_all(self) -> List[LoadedPlugin]:
        root = self._root()
        if not root.exists():
            return []

        loaded: List[LoadedPlugin] = []
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
                spec = json.loads(spec_path.read_text(encoding="utf-8"))

                ok, err = self.validator.validate("plugin_spec", spec, raise_on_error=False)
                if not ok:
                    raise ValidationError(f"Invalid plugin_spec at {spec_path}: {err}")

                # parse scope from path parts
                parts = install_dir.relative_to(root).parts
                if len(parts) < 4:
                    continue
                tenant_id, workspace_id, plugin_name, version = parts[0], parts[1], parts[2], parts[3]

                # load exported tools
                files_dir = install_dir / "files"
                tool_refs: List[str] = []
                exported_tools = (spec.get("exports") or {}).get("tools") or []
                for tool_ref in exported_tools:
                    tool_spec_path = files_dir / "tools" / f"{tool_ref.split(':',2)[2]}.json"
                    if not tool_spec_path.exists():
                        continue
                    try:
                        tool_spec = json.loads(tool_spec_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    ok2, err2 = self.validator.validate("tool_spec", tool_spec, raise_on_error=False)
                    if not ok2:
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
                    )
                )
            except Exception:
                # Loader should be best-effort; do not crash the app on a single bad plugin.
                continue

        return loaded
