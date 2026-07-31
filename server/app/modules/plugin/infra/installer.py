"""Plugin installation pipeline."""

from __future__ import annotations

import io
import json
import logging
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.kernel.registry.signature import (
    payload_digest,
    sha256_hex,
    verify_sha256,
    verify_signature,
)
from app.kernel.specs.validator import SpecValidator
from app.settings.settings import get_settings

logger = logging.getLogger(__name__)

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


def _load_manifest_from_dir(install_dir: Path) -> dict[str, Any]:
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

    def _check_revocation(self, digest: str) -> None:
        """Refuse a revoked package before trusting its signature.

        A revoked artifact is normally one that was correctly signed, so this
        must be checked independently of verification rather than after it.
        """
        revoked = self.settings.plugin_revoked_package_digests or []
        if not revoked:
            return
        normalized = digest.strip().lower()
        for entry in revoked:
            candidate = (entry or "").strip().lower()
            if candidate.startswith("sha256:"):
                candidate = candidate.split(":", 1)[1]
            if candidate and candidate == normalized:
                raise ValidationError("Plugin package digest is revoked.")

    def _check_integrity(
        self,
        *,
        spec: dict[str, Any],
        digest: str,
        package_bytes: bytes | None = None,
    ) -> None:
        # Revocation names the exact artifact, so it uses the archive digest.
        self._check_revocation(digest)
        integrity = spec.get("integrity") or {}
        expected = (integrity.get("digest") or "").strip()
        # The declaration lives inside the archive, so it can only cover the
        # payload around it. Comparing it to the archive's own hash can never
        # hold: writing the value changes the thing being hashed.
        content_digest = (
            payload_digest(package_bytes) if package_bytes is not None else digest
        )
        if self.settings.plugin_integrity_required:
            # Skipping the check because nothing was declared would let a
            # package opt out of the requirement by staying silent.
            if not expected:
                raise ValidationError("Plugin package must declare an integrity digest.")
            expected_hex = expected.split(":", 1)[1] if expected.startswith("sha256:") else expected
            if expected_hex.lower() != content_digest.lower():
                raise ValidationError("Plugin package digest mismatch.")

        signature = (integrity.get("signature") or "").strip()
        if signature:
            public_keys = self.settings.plugin_signature_public_keys or []
            verified = False
            payload = (expected or f"sha256:{content_digest}").encode("utf-8")
            for key in public_keys:
                if verify_signature(data=payload, signature_b64=signature, public_key_b64=key):
                    verified = True
                    break
            if not verified:
                if self.settings.plugin_signature_required:
                    raise ValidationError("Plugin package signature verification failed.")
                logger.warning(
                    "plugin.signature.unverified",
                    extra={"plugin_name": spec.get("name"), "version": spec.get("version")},
                )
        elif self.settings.plugin_signature_required:
            raise ValidationError("Plugin package signature required.")

    def inspect_package(self, package_bytes: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
        """Inspect plugin package and return manifest/spec without installing."""
        digest = sha256_hex(package_bytes)
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            with zipfile.ZipFile(io.BytesIO(package_bytes), "r") as zf:
                _safe_extract_zip(zf, tmp_dir)

            extracted_root = tmp_dir
            children = list(tmp_dir.iterdir())
            if len(children) == 1 and children[0].is_dir():
                extracted_root = children[0]

            manifest = _load_manifest_from_dir(extracted_root)
            manifest.setdefault("enabled", True)
            spec = manifest.get("spec") or manifest.get("spec_json") or manifest.get("specJson")
            if not isinstance(spec, dict):
                spec_path = extracted_root / "spec.json"
                if spec_path.exists():
                    spec = json.loads(spec_path.read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                raise ValidationError("Plugin package missing spec (manifest.spec or spec.json).")

            issues = self.validator.validate("plugin_spec", spec, raise_on_error=False)
            if issues:
                raise ValidationError(f"Invalid plugin_spec: {issues[0].message}")

            self._check_integrity(spec=spec, digest=digest, package_bytes=package_bytes)

            return manifest, spec

    def install_from_bytes(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        plugin_name: str,
        version: str,
        package_bytes: bytes,
        expected_sha256: str | None = None,
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
        children = list(tmp_dir.iterdir())
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

        issues = self.validator.validate("plugin_spec", spec, raise_on_error=False)
        if issues:
            raise ValidationError(f"Invalid plugin_spec: {issues[0].message}")

        self._check_integrity(spec=spec, digest=digest, package_bytes=package_bytes)

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

            tool_issues = self.validator.validate("tool_spec", tool_spec, raise_on_error=False)
            if tool_issues:
                raise ValidationError(f"Invalid tool_spec for '{tool_ref}': {tool_issues[0].message}")

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

        logger.info(
            "plugin.install",
            extra={
                "plugin_name": plugin_name,
                "version": version,
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "tool_count": len(tool_refs),
                "install_dir": str(install_dir),
            },
        )

        return InstalledPluginPaths(
            package_path=package_path,
            install_dir=install_dir,
            manifest_path=manifest_path,
            spec_path=spec_path,
        )
