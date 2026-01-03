""" installer

Plugin installation pipeline.

Responsibilities
- Validate plugin spec/manifest (JSON Schema via kernel.specs).
- Persist package and extracted files to filesystem storage.
- Register installed plugin metadata into the in-process registry.

This module intentionally does NOT change DB schema.
Installation state (enabled/disabled etc.) should live in PluginInstallation.config_json.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.kernel.registry.signature import sha256_hex, verify_sha256
from app.kernel.specs.validator import SpecValidator
from app.settings.settings import get_settings


@dataclass(frozen=True)
class InstalledPluginPaths:
    package_path: Path
    install_dir: Path
    manifest_path: Path
    spec_path: Path


def _safe_join(root: Path, *parts: str) -> Path:
    p = (root / Path(*parts)).resolve()
    root_r = root.resolve()
    if not str(p).startswith(str(root_r)):
        raise ValidationError("Unsafe plugin path (path traversal).")
    return p


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    for member in zf.infolist():
        name = member.filename
        # block absolute paths and traversal
        if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
            raise ValidationError(f"Unsafe zip entry: {name}")
    zf.extractall(dest)


def _load_manifest_from_dir(install_dir: Path) -> Dict[str, Any]:
    """Load manifest from an extracted plugin directory."""
    # priority: plugin.json -> plugin.toml
    json_path = install_dir / "plugin.json"
    toml_path = install_dir / "plugin.toml"

    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))
    if toml_path.exists():
        if tomllib is None:
            raise ValidationError("plugin.toml found but tomllib unavailable.")
        return tomllib.loads(toml_path.read_text(encoding="utf-8"))

    raise ValidationError("Plugin package missing plugin.json (or plugin.toml).")


class PluginInstaller:
    """Filesystem-backed plugin installer."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.validator = SpecValidator()

    def _root(self) -> Path:
        return Path(self.settings.plugins_dir).resolve()

    def install_from_bytes(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        plugin_name: str,
        version: str,
        package_bytes: bytes,
        expected_sha256: Optional[str] = None,
    ) -> InstalledPluginPaths:
        """Install a plugin package (zip bytes) into filesystem and register it."""

        if expected_sha256:
            if not verify_sha256(package_bytes, expected_sha256):
                raise ValidationError("Plugin package sha256 mismatch.")

        digest = sha256_hex(package_bytes)

        root = self._root()
        packages_dir = _safe_join(root, "packages", tenant_id, workspace_id, plugin_name, version)
        install_dir = _safe_join(root, "installed", tenant_id, workspace_id, plugin_name, version)

        packages_dir.mkdir(parents=True, exist_ok=True)
        install_dir.mkdir(parents=True, exist_ok=True)

        package_path = packages_dir / f"{plugin_name}-{version}.zip"
        package_path.write_bytes(package_bytes)

        # extract to temp then swap (avoid half-installed dirs)
        tmp_dir = install_dir.parent / f".tmp_{plugin_name}_{version}"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(package_bytes), "r") as zf:
            _safe_extract_zip(zf, tmp_dir)

        # allow package to contain a single top folder
        extracted_root = tmp_dir
        children = [p for p in tmp_dir.iterdir()]
        if len(children) == 1 and children[0].is_dir():
            extracted_root = children[0]

        manifest = _load_manifest_from_dir(extracted_root)
        manifest.setdefault("enabled", True)
        spec = manifest.get("spec") or manifest.get("spec_json") or manifest.get("specJson")
        if not isinstance(spec, dict):
            # also allow separate spec.json
            spec_path = extracted_root / "spec.json"
            if spec_path.exists():
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValidationError("Plugin package missing spec (manifest.spec or spec.json).")

        ok, err = self.validator.validate("plugin_spec", spec, raise_on_error=False)
        if not ok:
            raise ValidationError(f"Invalid plugin_spec: {err}")

        # persist manifest/spec as normalized json
        manifest_path = install_dir / "manifest.json"
        spec_path = install_dir / "spec.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

        # move extracted files into install_dir/files
        files_dir = install_dir / "files"
        if files_dir.exists():
            shutil.rmtree(files_dir, ignore_errors=True)
        shutil.move(str(extracted_root), str(files_dir))

        # cleanup tmp
        shutil.rmtree(tmp_dir, ignore_errors=True)

        # register into in-process registry (runtime lookup)
        reg = get_registry()

        # register exported tools (tool specs live under files/tools/<tool_name>.json)
        tool_refs: list[str] = []
        exported_tools = (spec.get("exports") or {}).get("tools") or []
        for tool_ref in exported_tools:
            # tool_ref format: tool:{adapter}:{tool_name_or_id}
            parts = tool_ref.split(":", 2)
            if len(parts) != 3:
                raise ValidationError(f"Invalid tool_ref in exports.tools: {tool_ref}")
            _, adapter, tool_name = parts

            tool_spec_path = files_dir / "tools" / f"{tool_name}.json"
            if not tool_spec_path.exists():
                raise ValidationError(
                    f"Plugin exports tool '{tool_ref}' but tool spec file not found: {tool_spec_path}"
                )
            try:
                tool_spec = json.loads(tool_spec_path.read_text(encoding="utf-8"))
            except Exception as e:
                raise ValidationError(f"Failed to load tool spec json for '{tool_ref}': {e}")

            ok2, err2 = self.validator.validate("tool_spec", tool_spec, raise_on_error=False)
            if not ok2:
                raise ValidationError(f"Invalid tool_spec for '{tool_ref}': {err2}")

            reg.register(
                kind="tool",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                name=tool_ref,
                version=version,
                payload={
                    "tool_spec": tool_spec,
                    "plugin": {
                        "name": plugin_name,
                        "version": version,
                    },
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
                "sha256": digest,
                "install_dir": str(install_dir),
                "manifest": manifest,
                "spec": spec,
                "tools": tool_refs,
            },
        )

        return InstalledPluginPaths(
            package_path=package_path,
            install_dir=install_dir,
            manifest_path=manifest_path,
            spec_path=spec_path,
        )
