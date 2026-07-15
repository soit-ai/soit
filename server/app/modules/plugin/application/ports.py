"""Application-layer ports for the plugin module."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginRelease,
    PluginVersion,
)


class PluginRepositoryPort(Protocol):
    def get(self, plugin_id: str) -> Plugin | None: ...
    def get_by_name(self, name: str) -> Plugin | None: ...
    def get_by_name_version(self, name: str, version: str) -> Plugin | None: ...
    def create(self, plugin: Plugin) -> Plugin: ...
    def update(self, plugin: Plugin) -> Plugin: ...
    def delete(self, plugin: Plugin) -> None: ...
    def list(
        self,
        published_only: bool = False,
        plugin_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Plugin]: ...


class PluginInstallationRepositoryPort(Protocol):
    def get(self, installation_id: str) -> PluginInstallation | None: ...
    def get_by_plugin(self, plugin_id: str) -> PluginInstallation | None: ...
    def create(self, installation: PluginInstallation) -> PluginInstallation: ...
    def update(self, installation: PluginInstallation) -> PluginInstallation: ...
    def delete(self, installation: PluginInstallation) -> None: ...
    def list_by_workspace(self, limit: int = 100, offset: int = 0) -> Sequence[PluginInstallation]: ...
    def list_by_plugin(self, plugin_id: str) -> Sequence[PluginInstallation]: ...


class PluginVersionRepositoryPort(Protocol):
    def next_version_number(self, plugin_id: str) -> int: ...
    def get_by_id(self, version_id: str) -> PluginVersion | None: ...
    def create(self, version: PluginVersion) -> PluginVersion: ...
    def update(self, version: PluginVersion) -> PluginVersion: ...
    def list_by_plugin(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> Sequence[PluginVersion]: ...


class PluginReleaseRepositoryPort(Protocol):
    def create(self, release: PluginRelease) -> PluginRelease: ...
    def list_by_plugin(self, plugin_id: str, *, limit: int = 20, offset: int = 0) -> Sequence[PluginRelease]: ...


class PluginProjectionRepositoryPort(Protocol):
    def get_by_ref(self, *, plugin_id: str, artifact_ref: str) -> PluginInstalledArtifact | None: ...
    def create(self, artifact: PluginInstalledArtifact) -> PluginInstalledArtifact: ...
    def update(self, artifact: PluginInstalledArtifact) -> PluginInstalledArtifact: ...
    def list(
        self,
        *,
        plugin_id: str | None = None,
        artifact_kind: str | None = None,
        enabled: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[PluginInstalledArtifact]: ...
    def list_by_installation(self, installation_id: str) -> Sequence[PluginInstalledArtifact]: ...


class InstalledPluginPathsPort(Protocol):
    package_path: Path
    install_dir: Path
    manifest_path: Path
    spec_path: Path


class PluginInstallerPort(Protocol):
    """Port for plugin installation/extraction.

    Application code depends on this protocol so we can swap installation
    strategies (filesystem, object storage, remote runtime) without changing
    application logic.
    """

    def inspect_package(self, package_bytes: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return manifest and spec from plugin package bytes without installing."""
        ...

    def install_from_bytes(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        plugin_name: str,
        version: str,
        package_bytes: bytes,
        expected_sha256: str | None = None,
    ) -> InstalledPluginPathsPort:
        """Install plugin package bytes and return normalized package paths."""
        ...
